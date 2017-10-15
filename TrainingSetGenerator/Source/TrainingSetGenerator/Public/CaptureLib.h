// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "CaptureLib.generated.h"

/**
 * 
 */
UCLASS()
class TRAININGSETGENERATOR_API UCaptureLib : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
	
	public:

	//Screenshot to File
	UFUNCTION(BlueprintCallable, Category = "ScreenshotToFile")
	static bool ScreenshotToFile(FString SaveDirectory, FString FileName, bool debugOutput);
	
	
	
};
