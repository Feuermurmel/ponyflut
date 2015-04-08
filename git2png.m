{inFile, outDir} = $ScriptCommandLine[[2;;]];
MapIndexed[Export[outDir <> "/" <> IntegerString[#2[[1]], 10, 4] <> ".png", #1] &, Import[inFile]];
