#pragma once

#include "Engine.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Segmentation.generated.h"


/**
 * @author Timm Hess
 *
 * Segmentation BlueprintLibrary currently holds all custom UEBlueprintNodes for the UETrainingSet Generator that need high performance or weren't directly
 * supported by UE4
 */
UCLASS()
class TRAININGSETGENERATOR_API USegmentation : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
	public:
	//HELPER_NODES
	UFUNCTION(BlueprintCallable, Category = "SaveTextToFile")	
	static bool FileIO__SaveStringTextToFile(bool useStandardMaskSaveDir, FString SaveDirectory, FString JoyfulFileName, FString SaveText, bool AllowOverWriting = false);

	UFUNCTION(BlueprintCallable, Category = "NormalDistribution")
	static float getNormalDist(float mean = 0.0, float stddev= 1.0);
	
	//SEGMENTATION
	typedef struct {
		int32 X;
		int32 Y;
	} IntSize;

	UFUNCTION(BlueprintCallable, Category = "ImageSegmentation")
	static FString CaptureSegmentation(UObject* WorldContextObject, APlayerController const* Player, const int32 sizeX, const int32 sizeY, int32 stride, TArray<AActor*> objects, int32 nObjects, bool verbose);
	
	//UFUNCTION(BlueprintCallable, Category = "ImageSegmentationWithLocation")
	//static void CaptureSegmentationTwo(UObject* WorldContextObject, APlayerController const* Player, const int32 sizeX, const int32 sizeY, int32 stride, TArray<AActor*> objects, int32 nObjects, bool verbose, FString& testString, FString& hitLoaction);




};
