print('Hello! Python is up and running.')
import time
start = time.time()

import os
import io
import zipfile

datadir = "./data"
outputdata = ""

def extract (filename):
    outputdata = ""
    zip = zipfile.ZipFile(filename)
    for file in zip.namelist():
        if (os.path.splitext(file)[1]).lower() == ".dat":
            outputdata = outputdata + zip.read(file).decode("utf-8")
        elif (os.path.splitext(file)[1]).lower() == ".zip":
            zipInner = zipfile.ZipFile(io.BytesIO(zip.read(file)))
            for file2 in zipInner.namelist():
                if (os.path.splitext(file2)[1]).lower() == ".dat":
                    outputdata = outputdata + (zipInner.read(file2)).decode("utf-8")
                else:
                    print("Ignored file - " + file2)
        else:
            print("Ignored file - " + file)

    return outputdata

for file in os.listdir(datadir):
    filename = os.fsdecode(file)
    if filename.endswith(".zip"):
        print("Extracting " + datadir + "/" + filename)
        outputdata = outputdata + extract(datadir + "/" + filename)

print("Writing extract file")
f = open("extract.txt", "w+")
f.write(outputdata)
f.close()
print("Now compacting the data - " + str(int(time.time() - start)) + " seconds")

outputfile = ""
for line in outputdata.splitlines():
    if line[0:1] == "B":
        outputfile = outputfile + "\n" + line
    elif line[0:1] == "B":
        outputfile = outputfile + line


f = open("extract-compact.txt", "w+")
f.write(outputfile)
f.close()

print("Now processing the data - " + str(int(time.time() - start)) + " seconds")
#import process.py




