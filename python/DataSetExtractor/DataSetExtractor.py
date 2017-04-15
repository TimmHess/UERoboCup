from optparse import OptionParser
import os
import re
import sys
import time
import random
import math
import time

try: 
    import numpy as np
except:
    print("No numpy installation found..");
    sys.exit();

try:
    import cv2
except:
    print("No OpenCv(cv2) installation found..");
    sys.exit();



#####
#for ctrl-c close
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)
#####


#This function is used for numerical sorting of file names (strings)
numbers = re.compile(r'(\d+)');
def numericalSort(value):    
    parts = numbers.split(value)
    parts[1::2] = map(int, parts[1::2])
    return parts


def update_progress(message, progress):
    sys.stdout.write('\r');
    sys.stdout.write(message + "[%-50s] %d%%" % ('='*int(np.floor(0.5*progress)), 1*progress));
    sys.stdout.flush();


class DataSetExtractor():
    def __init__(self, pathToImages, pathToGroundTruth, patchSize, dbTargetPath):
        self.pathToImages = pathToImages;
        self.pathToGroundTruth = pathToGroundTruth;
        self.patchSize = patchSize;
        self.dbTargetPath = dbTargetPath;

        self.imageNames = sorted(self.__loadFileNames(pathToImages, ".png"), key=numericalSort);
        self.maskNames = sorted(self.__loadFileNames(pathToGroundTruth, ".txt"), key=numericalSort);
        self.legendFileName = self.__loadFileNames(pathToGroundTruth, ".leg");

        self.labelDict = self.__loadLabelConfig();
        self.legendDict = self.__readLegendFile();

        self.imageArray = None;
        self.labelArray = None;
        return;

    #################################################
    #PUBLIC:
    #################################################
    def extractDataSet(self, isPatchNumberEvening=False, maxPatchNumPerClass=[1,1,1,2], rgbFormat=False):
        """
        Extracts dataset using all images and masks available in the given directory.
        Use the "useOnePatchPerClass" variable if needed to even out the data sets per class
        distribution.
        """
        allPatchArray = [];
        allLabelArray = [];
        numImages = len(self.imageNames);
        for i in range(numImages):
            currImageArray, currLabelArray = self.extractPatchesForSingleImage(i);
            for j in range(len(currImageArray)):
                allPatchArray.append(currImageArray[j]);
                allLabelArray.append(currLabelArray[j]);
            progress = int(np.floor(i/float(numImages-1)*100));
            update_progress("Images processed: ",progress);
        print("\n");
        
        #double the number of goalposts
        self.__doVFlipForImageWithLabel(allPatchArray, allLabelArray, 3);

        #even the number of examples per class in the data set
        if(isPatchNumberEvening):
            allPatchArray, allLabelArray = self.__evenPatchNumbers(allPatchArray, allLabelArray);

        if(not rgbFormat):
            #prepare image crops for LMDB
            allPatchArray, allLabelArray = self.__transformImagesForTraining(allPatchArray, allLabelArray);

            #rewrite arrays as numpy arrays
            allPatchArray = np.asarray(allPatchArray, dtype="uint8");
            allLabelArray = np.asarray(allLabelArray, dtype="int64");
        else:
            allPatchArray, allLabelArray = self.__resizeImages(allPatchArray, allLabelArray);

        return allPatchArray, allLabelArray;


    def extractPatchesForSingleImage(self, imageIndex):
        #get image and mask for given imageIndex
        currMaskName = self.maskNames[imageIndex];
        currImageName = self.imageNames[imageIndex];
        currImage = cv2.imread(self.pathToImages + currImageName);

        #load mask into array structure
        currMaskArray = self.__processMask(currMaskName, currImage.shape[0]);
        currBoundingBoxMap = self.__extractAllBoundingBoxes(currMaskArray);
        currBoundingBoxMap = self.__agumentBoundingBoxes(currBoundingBoxMap);

        #generate image patches from currBoundingBoxMap
        currImageArray, currLabelArray = self.__generateImageCrops(currImage, currBoundingBoxMap);

        #generated random crop for "background"-class from image
        currRandomBackgroundPatch, backgroundLabel = self.__getRandomBackgroundPatch(currImage, currMaskArray, label=0);
        #append currRandomBackgroundPatch to array
        currImageArray.append(currRandomBackgroundPatch);
        currLabelArray.append(backgroundLabel);

        #prepare image crops for LMDB
        #currImageArray, currLabelArray = self.__transformImagesForTraining(currImageArray, currLabelArray);
        
        #change image and label array data format(needed when this function is used alone)
        #currImageArray = np.asarray(currImageArray, dtype="uint8");
        #currLabelArray = np.asarray(currLabelArray, dtype="int64");
        return currImageArray, currLabelArray;


    def saveToLMDB(self, imageArray, labelArray):
        """
        Saves given imageArray(uint8) and labelArray(int64)
        to LMDB file
        """
        map_size = imageArray.nbytes * 10;
        print("Space needet: " + str(imageArray.nbytes/1000.0/1000.0) + " mb...");
        #open database file
        env = lmdb.open(self.dbTargetPath, map_size=map_size);
        #write given examepls and labels to database
        with env.begin(write=True) as txn: #txn = transaction object
            for i in range(len(imageArray)):
                print("creating Datum: " + str(i));
                currDatum = caffe.proto.caffe_pb2.Datum();
                currDatum.channels = imageArray.shape[1];
                currDatum.height = imageArray.shape[2];
                currDatum.width = imageArray.shape[3];

                currDatum.data = imageArray[i].tobytes();
                currDatum.label = int(labelArray[i]);
                str_id = "{0:08}".format(i);
                
                txn.put(str_id, currDatum.SerializeToString());


    def saveToDirStructure(self, imageArray, labelArray):
        """
        Saves given imageArray(uint8) and labelArray(int64)
        to a sub-directory structure
        """
        dirNameDict = {0:"/background", 1:"/ball", 2:"/robot", 3:"/goalpost"};

        #create subdirs based on dirNameDict
        self.__createSubDirs(dirNameDict);

        #save image patches to sub-dir structure
        for i in range(len(imageArray)):
            currImagePath = self.dbTargetPath+dirNameDict[labelArray[i]]+"/img"+str(i)+".png";
            cv2.imwrite(currImagePath, imageArray[i]);

        return;


    #################################################
    #Private
    #################################################
    def __resizeImages(self, imageArray, labelArray):
        resizedImageArray = [];
        for img in imageArray:
            img = cv2.resize(img, (self.patchSize,self.patchSize));
            resizedImageArray.append(img);

        return resizedImageArray, labelArray;
    
    def __transformImagesForTraining(self, imageArray, labelArray):
        """
        Warps image crops to match the given network input and change image
        data structure (e.g. from [32,32,3] to [3,32,32]).
        """
        transformedImageArray = [];
        for img in imageArray:
            img = cv2.resize(img, (self.patchSize,self.patchSize));
            img = np.asarray([img[:,:,0],img[:,:,1],img[:,:,2]]);
            transformedImageArray.append(img);

        return transformedImageArray, labelArray;


    def __generateImageCrops(self, image, bbMap):
        """
        Crops all patches given by bbMap from given image
        """
        imageArray = [];
        labelArray = [];
        for key in bbMap:
            startX, startY, endX, endY = bbMap[key];
            currImageBB = image[startY:endY, startX:endX];
            currLabel = self.__getLabel(key);
            imageArray.append(currImageBB);
            labelArray.append(currLabel);

        return imageArray, labelArray;

    def __doVFlipForImageWithLabel(self, imageArray, labelArray, label):
        """
        Applies vflip to every image with given label.
        """
        lenImageArray = len(imageArray);
        for i in range(lenImageArray):
            if(label == labelArray[i]):
                currImage = imageArray[i];
                flipImage = cv2.flip(currImage, 1);
                imageArray.append(flipImage);#vflip
                labelArray.append(label);


    def __evenPatchNumbers(self, imageArray, labelArray):
        evenImageArray = [];
        evenLabelArray = [];
        #devide image patches by label
        imageDict = {};
        for i in range(len(imageArray)):
            if(not labelArray[i] in imageDict):
                imageDict[labelArray[i]] = [];
                imageDict[labelArray[i]].append(imageArray[i]);
            else:
                imageDict[labelArray[i]].append(imageArray[i]);

        #get class with minimum patches
        classCounterArray = [];
        for key in imageDict:
            classCounterArray.append(len(imageDict[key]));
        print(classCounterArray);
        maxPatchNumPerClass = min(classCounterArray);

        #extract the given number of random patches for each class
        for key in imageDict:
            currEvenBatch, currEvenLabels = self.__extractRandomPatchesUniform(imageDict[key], key, maxPatchNumPerClass);
            print(len(currEvenBatch));
            evenImageArray += currEvenBatch;
            evenLabelArray += currEvenLabels;

        return evenImageArray, evenLabelArray;

    def __extractRandomPatchesUniform(self, imageArray, label, numberOfPatches):
        """
        Extracts 'numberOfPatches' elements using a uniform-distribution from the given 'imageArray'.
        @see __evenPatchNumbers()
        """
        newImageArray = [];
        newLabelArray = [];
        lenImageArray = len(imageArray) -1;
        #check for out of bounds error
        if(numberOfPatches-1 > lenImageArray):
            print("Cannot extract " + str(numberOfPatches)+" patches from image array of length " + str(lenImageArray));
            sys.exit();

        for i in range(numberOfPatches):
            currRandomIndex = int(np.floor(np.random.uniform(0,lenImageArray)));
            newImageArray.append(imageArray.pop(currRandomIndex));
            newLabelArray.append(label);
            lenImageArray -= 1;

        return newImageArray, newLabelArray;


    def __loadLabelConfig(self):
        """
        Reads LabelConfig.txt to dictionary
        """
        labelDict = {};
        with open("./LabelConfig.txt") as file:
            data = file.readlines();
            data = [x.replace("\n","") for x in data];
            data = [x.split(":") for x in data];
            for i in data:
                labelDict[i[0]] = i[1];

        return labelDict;


    def __loadFileNames(self, filesPath, extention, isSorted=True, sortingCriterion=None):
        """
        Load all file names in the given directory with the given extention into a list
        """
        print("loading files: " + extention);
        fileList = [];
        #if any files in folder
        if(len(os.walk(filesPath).next()[2]) > 0): #1:folder, 2:files
            allFileList = os.walk(filesPath).next()[2];
            #print(allFileList);
            for file in allFileList:
                if(file.endswith(extention)):
                    fileList.append(file);

        if(isSorted):
            return sorted(fileList, sortingCriterion);

        return fileList;


    def __readLegendFile(self):
        """
        Loads the legend file generated by UETrainingSetGenerator into a 
        dictionary structure
        """
        legendDict = {};
        with open(self.pathToGroundTruth + self.legendFileName[0], "r") as currFile:
            fileData = currFile.readline().split(" ");
            currLegendIndex = 0;
            for i in fileData:
                i = i.split(":");
                if(len(i) < 2): #catching occunring whitespaces at file endings
                    continue;

                currLegendIndex += int(i[0]);
                legendDict[str(currLegendIndex)] = i[1]
        return legendDict;


    def __getTag(self, key):
        legendKeyArray = sorted(map(int, self.legendDict.keys()));
        for legendKey in legendKeyArray:
            if(key-1 < legendKey):
                return (self.legendDict[str(legendKey)]);

    def __getLabel(self, key):
        currTag = self.__getTag(key);
        return(int(self.labelDict[currTag]));


    def __boundingBoxSanityCheck(self, startXpos, startYpos, endXpos, endYpos):
        """
        Check for too small bounding boxes 
        """
        if((endXpos - startXpos) <= 20):
            return False;
        if((endYpos - startYpos) <= 20):
            return False;
        return True;


    def __extractAllBoundingBoxes(self, maskArray):
        """
        Extracts all bounding boxes from the given maskArray
        based on the semantic segmentation given by the mask
        """
        bbMap = {};

        startXpos = 3000;
        startYpos = 3000;
        endXpos = 0;
        endYpos = 0;

        #run through all "pixels" of the maskArray
        for y in range(len(maskArray)):
            for x in range(len(maskArray[y])):
                #get currIndex from current maskFile
                if(bool(re.search(r'\d', maskArray[y][x]))):
                    currIndex = int(maskArray[y][x]);
                    if(currIndex == 0):
                        continue;
                else:
                    continue;

                #if currIndex has not been already seen -> add map entry
                if(not(currIndex in bbMap)):  
                    bbMap[currIndex] = [startXpos, startYpos, endXpos, endYpos];

                #if currIndex has been seen -> update map entry
                if(currIndex in bbMap):            
                    if(x < bbMap[currIndex][0]):    #startXpos
                        bbMap[currIndex][0] = x;
                    if(x > bbMap[currIndex][2]):    #endXpos
                        bbMap[currIndex][2] = x;
                    if(y < bbMap[currIndex][1]):    #startYpos
                        bbMap[currIndex][1] = y;
                    if(y > bbMap[currIndex][3]):    #endYpos
                        bbMap[currIndex][3] = y;

        #check for overlappings in patches for fieldmarkings and goalposts
        #if any overlapping is found -> for now: this patch is omitted //TODO: Change to IOU function
        killArray = [];
        for key in bbMap:
            if(self.__getTag(key) == "fieldmarkings" or self.__getTag(key) == "goalpost"):
                stop = False;
                startX, startY, endX, endY = bbMap[key];
                for y in range(startY, endY):
                    if(stop == True):
                        break;
                    for x in range(startX, endX):
                        if(stop == True):
                            break;
                        currIndex = int(maskArray[y][x]);
                        if(currIndex != 0 and self.__getTag(currIndex) != self.__getTag(key)):
                            killArray.append(key);
                            stop = True;

        for key in killArray:
            del bbMap[key];

        return bbMap;


    def __agumentBoundingBoxes(self, bbMap):
        """
        Applies small shifts in position and size to the bounding box to prevent 
        centered object positions thoughout the generated data set
        """
        killArray = [];
        for key in bbMap:
            startXpos, startYpos, endXpos, endYpos = bbMap[key];
            if(not self.__boundingBoxSanityCheck(startXpos,startYpos,endXpos,endYpos)):
                killArray.append(key);
                continue;

            if(self.__getTag(key) == "ball"): #ball
                #random scale bounding box
                r = random.uniform(-0.2,1);
                randomOffset = int(r * 10);
                startXpos = startXpos - randomOffset;
                startYpos = startYpos - randomOffset;
                endXpos = endXpos + randomOffset;
                endYpos = endYpos + randomOffset;
                
                #get width and height of current bounding box
                currWidth = abs(startXpos-endXpos);
                currHeight = abs(startYpos-endYpos);

                #random translate bounding box
                rX = random.uniform(-0.25, 0.25); #random x translation factor
                rY = random.uniform(-0.25, 0.25); #random y translation factor
                rX *= currWidth;
                rY *= currHeight;
                if(not(startXpos + rX < 0 or startXpos + rX >= 640)):
                    if(not(startYpos + rY < 0 or startYpos +rY >= 480)):
                        startXpos += rX;
                        startYpos += rY;
                        endXpos += rX;
                        endYpos += rY;
                
            if(self.__getTag(key) == "crossing"): 
                #random scale bounding box
                r = random.uniform(0,1);
                randomOffset = int(r * 50);
                startXpos = startXpos - randomOffset;
                startYpos = startYpos - randomOffset;
                endXpos = endXpos + randomOffset;
                endYpos = endYpos + randomOffset;


            if(self.__getTag(key) == "fieldmarkings"): 
                startXpos, startYpos, endXpos, endYpos = self.__randomCropBoundingBox(startXpos, startYpos, endXpos, endYpos);
                
            #prevent bounding box breaking image borders
            if(startXpos < 0):
                startXpos = 0;
            if(startYpos < 0):
                startYpos = 0;
            if(endXpos > 640):
                endXpos = 640;
            if(endYpos > 480):
                endYpos = 480;

            #return values to bbMap
            bbMap[key] = [int(startXpos), int(startYpos), int(endXpos), int(endYpos)];

        #delete all entries that failed the sanity check
        for key in killArray:
            bbMap.pop(key, None);

        return bbMap;

    def __getRandomBackgroundPatch(self, image, maskArray, label=0, maxWidth=256, maxHeight=256):
        """
        Cuts random bounding box from image where no other class is overlapping.
        """
        isFound = False;
        startXpos = None;
        startYpos = None;
        endXpos = None;
        endYpos = None;

        imgWidth = image.shape[1];
        imgHeight = image.shape[0];
        #search for random patch that is no containing too much of other classes
        while(not isFound):
            #get random number between 0 and 1
            r = random.uniform(0.1,1);
            #apply random crop to max bounding box
            bbWidth = int(math.floor(r * maxWidth));
            bbHeight = int(math.floor(r * maxHeight));
            #get random bounding box "start points" (top-left-corner)
            startXpos = int(random.randint(0,imgWidth-1));
            startYpos = int(random.randint(0,imgHeight-1));
            endXpos = int(startXpos + bbWidth);
            endYpos = int(startYpos + bbHeight);
            #prevent out of bounds exception
            if(endXpos >= imgWidth or endYpos >= imgHeight):
                continue;
            
            notFieldCounter = 0;
            for y in range(startYpos, (endYpos-1)):
                for x in range(startXpos, (endXpos-1)):
                    #search bounding box for object pixels, if too many object pixels -> search for new bounding box
                    if(int(maskArray[y][x]) != 0):
                        notFieldCounter += 1;

            bbArea = ((endXpos - startXpos) * (endXpos - startXpos)) + ((endYpos - startYpos) * (endYpos - startYpos));
            
            if(notFieldCounter <= (bbArea * 0.01)):
                isFound = True;

        #cut patch from image
        currPatch = image[startYpos:endYpos, startXpos:endXpos];

        return currPatch, label;


    def __createSubDirs(self, dirNameDict):
        #create root dir
        if(not os.path.exists(self.dbTargetPath)):
            os.makedirs(self.dbTargetPath);

        #create all dirs corresponding to tags
        for key in dirNameDict:
            os.makedirs(self.dbTargetPath + dirNameDict[key]);

        return;


    def __randomCropBoundingBox(self, startXpos, startYpos, endXpos, endYpos):
        """
        Cuts a random crop from inside a given bounding box bounds.
        The minimum size of the random crop area is the given patchsize
        """
        if(abs(startXpos-endXpos) > self.patchSize and abs(startYpos-endYpos) > self.patchSize):
            #get top-left random point in bounding box with respect to patch size
            x1 = np.random.uniform(startXpos, endXpos-self.patchSize);
            y1 = np.random.uniform(startYpos, endYpos-self.patchSize);

            #get width and height of maximum bounding box with respect to x1 and y1
            w1 = abs(x1 - endXpos);
            h1 = abs(y1 - endYpos);

            #get bottom-right random point
            x2 = np.random.uniform(x1,(x1+w1)-self.patchSize) + self.patchSize;
            y2 = np.random.uniform(y1,(y1+h1)-self.patchSize) + self.patchSize;

            return x1, y1, x2, y2;

        return startXpos, startYpos, endXpos, endYpos;


    def __processMask(self, maskName, imageHeight):
        """
        Processes given maskFile into 2d-array structure.
        """
        maskArray = [];
        with open(self.pathToGroundTruth + maskName, "r") as currFile:
            for i in range(imageHeight): #480
                #read line from segMaskFile
                currLineData = currFile.readline();
                #gather segNames from File
                currLineData = currLineData.split(" ");
                maskArray.append(currLineData); 
        return maskArray;




#########################################################
#Program
#########################################################
if(__name__ == "__main__"):
    argv = sys.argv;

    parser = OptionParser();
    parser.add_option("-i", "--imgData", action="store", type="string", dest="pathToImages");
    parser.add_option("-g", "--groundTruth", action="store", type="string", dest="pathToGroundTruth");
    parser.add_option("-p", "--patchSize", action="store", type="int", dest="patchSize", default=32);
    parser.add_option("-s", "--saveTo", action="store", type="string", dest="pathToDB", default="./DB");
    parser.add_option("--saveAs", action="store", type="string", dest="saveAs", default="LMDB");
    (options, args) = parser.parse_args(sys.argv);

    DATA_SET_SOURCE = options.pathToImages;
    GT_SOURCE = options.pathToGroundTruth
    PATCH_SIZE = options.patchSize;
    TARGET_DB = options.pathToDB;
    SAVE_AS = options.saveAs;

    print("");
    if(DATA_SET_SOURCE != None):
        print("Loading images from: "  + DATA_SET_SOURCE);
    else:
        print("No path to images given...");
        print("use -h for help");
        sys.exit(0);
    if(GT_SOURCE != None):
        print("Loading ground truth from: " + GT_SOURCE);
    else:
        print("No path to ground truth data given...");
        print("use -h for help");
    print("Using patch size: " + str(PATCH_SIZE) + "*" + str(PATCH_SIZE));
    print("Saving data set to: " + TARGET_DB);
    print("Saving data as: " + SAVE_AS);
    print("");

    time.sleep(2);

    dataSetExtractor = DataSetExtractor(DATA_SET_SOURCE, GT_SOURCE, PATCH_SIZE, TARGET_DB);
    if(SAVE_AS == "LMDB"):
        try:
            import caffe
        except:
            print("No caffe(pyCaffe) installation found..");
            sys.exit();

        try:
            import lmdb
        except:
            print("No LMDB installation found..");
            sys.exit();

        imageArray, labelArray = dataSetExtractor.extractDataSet(isPatchNumberEvening=True, rgbFormat=False);
        dataSetExtractor.saveToLMDB(imageArray, labelArray);
    elif(SAVE_AS == "DIR"):
        imageArray, labelArray = dataSetExtractor.extractDataSet(isPatchNumberEvening=True, rgbFormat=True);
        dataSetExtractor.saveToDirStructure(imageArray, labelArray);