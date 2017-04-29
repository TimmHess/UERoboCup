import numpy as np
import lmdb
import caffe
import cv2
import sys


#####
#for ctrl-c close
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)
#####

argv = sys.argv;
print(len(argv));
if(len(argv) <=1):
	print("no dbpath given...");
	sys.exit();
if(len(argv) > 2):
	offset = int(argv[2]);
else:
	offset = 0;
dbPath = argv[1];

length = 0;
imageArray = [];
labelArray = [];

labelCountArray = [0,0,0,0];


env = lmdb.open(dbPath, readonly=True);
print("calculating number of entries in db...");
with env.begin() as txn:
	length = txn.stat()['entries']
	print("number of entries: " + str(length));

with env.begin() as txn:
	for i in range(offset, length):
		str_id = "{0:08}".format(i);
		#print(str_id);
		raw_datum = txn.get(str_id);

		datum = caffe.proto.caffe_pb2.Datum();
		datum.ParseFromString(raw_datum);

		flat_x = np.fromstring(datum.data, dtype=np.uint8);
		x = flat_x.reshape(datum.channels, datum.height, datum.width);
		y = datum.label;

		rgbArray = np.zeros((32,32,3), 'uint8');
		rgbArray[..., 0] = x[0,:,:];
		rgbArray[..., 1] = x[1,:,:];
		rgbArray[..., 2] = x[2,:,:];

		imageArray.append(rgbArray);
		labelArray.append(y);

		labelCountArray[y] += 1;

print(labelCountArray);
for i in range(len(imageArray)):
	print(labelArray[i]);
	cv2.imshow("image", imageArray[i]);
	cv2.waitKey();

print(len(imageArray));