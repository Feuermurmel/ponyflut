import sys, socket


def main(host = 'px6.nerdkunst.de', port = '1234'):
	sock = socket.socket(socket.AF_INET6)
	sock.connect((host, int(port)))
	
	file = sock.makefile('rwb')
	file.write(open('mirror.txt', 'rb').read()[:10000])
	file.flush()
	
	sock.close()


main(*sys.argv[1:])
