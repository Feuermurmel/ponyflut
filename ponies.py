import sys, os, socket, math, subprocess, queue, threading, contextlib, time, random, itertools


def log(message, *args):
	print(message.format(*args), file = sys.stderr)


def format_color(r, g, b):
	def format_value(b):
		return '{:02x}'.format(min(max(math.floor(b * 256), 0), 255))
	
	return ''.join(format_value(i) for i in [r, g, b])


class Display:
	def __init__(self, host, port):
		self._socket = socket.socket(socket.AF_INET6)
		self._socket.connect((host, port))
		self._file = self._socket.makefile('rw', encoding = 'utf-8')
		self._write_queue = queue.Queue()
		
		self._thread = threading.Thread(target = self._write_target, daemon = True)
		self._thread.start()
		
		self._size = self._get_size()
	
	def __enter__(self):
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		self._write_queue.put(None)
		self._thread.join()
		self.close()

	def _write_target(self):
		while True:
			elem = self._write_queue.get()
			
			if elem is None:
				break
			
			self._file.write(elem)
			self._file.flush()
	
	def _write(self, text):
		self._write_queue.put(text)
	
	def _read(self):
		line = self._file.readline()
		
		return line
	
	def _get_size(self):
		self._write('SIZE\n')
		token, x, y = self._read().split()
		
		assert token == 'SIZE'
		
		return int(x), int(y)
	
	def _is_valid_coord(self, coord):
		x, y = coord
		
		return x in range(self.size[0]) and y in range(self.size[1])
	
	def close(self):
		if self._socket is not None:
			self._socket.shutdown(socket.SHUT_RDWR)
			self._socket.close()
			self._socket = None
	
	def get_pixels(self, coords):
		result = { }
		valid_coords = []
		
		for i in sorted(coords):
			if self._is_valid_coord(i):
				valid_coords.append(i)
			else:
				result[i] = ''
		
		self._write(''.join('PX {} {}\n'.format(x, y) for x, y in valid_coords))
		
		for x, y in valid_coords:
			token, xr, yr, color = self._read().split()
			
			assert token == 'PX'
			assert int(xr) == x
			assert int(yr) == y
			
			result[(x, y)] = color[:6]
		
		return result
	
	def get_pixel(self, x, y):
		return self.get_pixels([(x, y)])[(x, y)]
	
	def set_pixels(self, pixels):
		valid_pixels = sorted([(k, v) for k, v in pixels.items() if self._is_valid_coord(k)])
		
		self._write(''.join('PX {} {} {}\n'.format(x, y, color) for (x, y), color in valid_pixels))
	
	def set_pixel(self, x, y, color):
		self.set_pixels({ (x, y): color })
	
	@property
	def size(self):
		return self._size


def command(*args):
	process = subprocess.Popen(args, stdout = subprocess.PIPE)
	output, _ = process.communicate()
	
	assert not process.returncode
	
	return output


def read_image(path):
	size_x, size_y, *crap = command('identify', '-format', '%[fx:w] %[fx:h] ', path).split()
	data = command('convert', '-depth', '8', path, 'rgba:')
	
	size_x = int(size_x)
	size_y = int(size_y)
	
	def fn():
		for y in range(size_y):
			for x in range(size_x):
				index = 4 * (size_x * y + x)
				part = data[index:index + 4]
				
				if part[3]:
					yield (x, y), ''.join('{:02x}'.format(i) for i in part[:3])
	
	return dict(fn())


def move_pixels(pixels, offset):
	return { vector_plus(i, offset): color for i, color in pixels.items() }


def vector_zip(fn, *args):
	return tuple(itertools.starmap(fn, zip(*args)))


def vector_plus(*args):
	return vector_zip(lambda *args: sum(args), *args)


def vector_times(factor, a):
	return tuple(factor * i for i in a)


def vector_minus(a, b):
	return vector_plus(a, vector_negate(b))


def vector_negate(a):
	return vector_zip(lambda a: -a, a)


def vector_min(*args):
	return vector_zip(min, *args)


def vector_max(*args):
	return vector_zip(max, *args)


def image_bounding_box(pixels):
	return vector_min(*pixels), vector_plus(vector_max(*pixels), (1, 1))


class PonyType:
	def __init__(self, dir_path, offset_per_image):
		self._path = dir_path
		self._images = [read_image(os.path.join(dir_path, i)) for i in sorted(os.listdir(dir_path)) if i.endswith('.png')]
		self._bounding_box = self._calculate_bounding_box()
		self._offset_per_image = offset_per_image
	
	def _calculate_bounding_box(self):
		min, max = zip(*[image_bounding_box(i) for i in self._images])
		
		return vector_min(*min), vector_max(*max)
	
	def get_frame(self, index):
		return self._images[index]
	
	@property
	def path(self):
		return self._path
	
	@property
	def offset_per_image(self):
		return self._offset_per_image
	
	@property
	def frame_count(self):
		return len(self._images)
	
	@property
	def bounding_box(self):
		return self._bounding_box


class Pony:
	def __init__(self, type : PonyType, display : Display, start_position):
		self._type = type
		self._display = display
		self._start_position = start_position
		
		self._current_frame = 0
		self._hold_pixels = self._get_hold_pixels()
		self._current_pixels = { }
	
	def _get_hold_pixels(self):
		_, offset_y = self._start_position
		(_, top), (_, bottom) = self._type.bounding_box
		right, _ = self._display.size
		pixels_to_hold = [(x, y + offset_y) for y in range(top, bottom) for x in range(right)]
		
		return self._display.get_pixels(pixels_to_hold)
	
	def step(self):
		self._current_frame += 1
	
	def paint(self):
		new_pixels = { k: v for k, v in move_pixels(self._type.get_frame(self._current_frame % self._type.frame_count), self.position).items() if self._display._is_valid_coord(k) }
		
		changed_pixels = { }
		
		for k, v in list(self._current_pixels.items()):
			v2 = new_pixels.get(k, self._hold_pixels[k])
			
			if v != v2:
				changed_pixels[k] = v2
				del self._current_pixels[k]
		
		for k, v in new_pixels.items():
			if v != self._current_pixels.get(k):
				changed_pixels[k] = v
				self._current_pixels[k] = v
		
		self._display.set_pixels(changed_pixels)
	
	def hide(self):
		self._display.set_pixels(self._hold_pixels)
		# self._hold_pixels.clear()
	
	@property
	def position(self):
		return vector_plus(self._start_position, vector_times(self._current_frame, self._type.offset_per_image))


@contextlib.contextmanager
def pony_context(pony : Pony):
	try:
		yield pony
	finally:
		pony.hide()


def load_pony(pony_images_dir, pony_def_file):
	with open(pony_def_file, 'r', encoding = 'utf-8') as file:
		offset = int(file.read())
	
	return PonyType(pony_images_dir, (offset, 0))


def mostly_random_sequence(choices, min_distance = None):
	if min_distance is None:
		min_distance = len(choices) // 2
	
	assert min_distance < len(choices)
	
	choices = set(choices)
	blacklist = []
	
	while True:
		choice = random.choice(list(choices - set(blacklist)))
		blacklist.append(choice)
		
		if len(blacklist) > min_distance:
			blacklist.pop(0)
		
		yield choice


def main(host = 'px6.nerdkunst.de', port = '1234'):
	pony_defs_dir = 'ponies_gif'
	pony_images_dir = 'ponies'
	pony_names = [i[:-4] for i in os.listdir(pony_defs_dir) if i.endswith('.txt')]
	# pony_names = ['fluttershy']
	
	log('Loading {} ponies ...', len(pony_names))
	ponies = [load_pony(os.path.join(pony_images_dir, i), os.path.join(pony_defs_dir, i + '.txt')) for i in pony_names]
	log('Done.')
	
	while True:
		try:
			with Display(host, int(port)) as d:
				frame_delay = 1 / 12
				current_time = time.time()
				screen_width, screen_height = d.size
				
				for type in mostly_random_sequence(ponies):
					current_time += random.random() * 5 + 2
					width, height = type.bounding_box[1]
					start_y = random.randrange(screen_height - height)
					reverse_dir = type.offset_per_image[0] < 0
					
					if reverse_dir:
						start_x = screen_width
					else:
						start_x = -width
					
					with pony_context(Pony(type, d, (start_x, start_y))) as pony:
						while pony.position[0] > -type.bounding_box[1][0] if reverse_dir else pony.position[0] < screen_width:
							current_time += frame_delay
							now = time.time()
							delay = current_time - now
							
							if delay > 0:
								time.sleep(delay)
							
							start = time.time()
							
							pony.step()
							pony.paint()
							
							log('{}: {}, painting took {:.2f} s.', type.path, pony.position, time.time() - start)
		except socket.error as e:
			log('{}', e)
			
			time.sleep(5)


try:
	main(*sys.argv[1:])
except KeyboardInterrupt:
	pass
