// Fill out your copyright notice in the Description page of Project Settings.

#include "TrainingSetGenerator.h"
#include "CaptureLib.h"


bool UCaptureLib::ScreenshotToFile(FString SaveDirectory, FString FileName, bool debugOutput) {

	FString currGameDir = FPaths::GameDir();
	FString filename = currGameDir + SaveDirectory + FileName;

	FScreenshotRequest::RequestScreenshot(filename, false, false);

	if (debugOutput) {
		GEngine->AddOnScreenDebugMessage(-1, 15.0f, FColor::Green, "Screenshot Done");
	}


	return true;
}


