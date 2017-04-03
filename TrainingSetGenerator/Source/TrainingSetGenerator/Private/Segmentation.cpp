/*
* @author Timm Hess
*/
#include "TrainingSetGenerator.h"
#include "Segmentation.h"
#include <random>
#include <cmath>

//###########################################################################
// STRING_TO_FILE by Rama("Victory Plugin")
//###########################################################################
/*
* @author Rama
* This function interfaces the UEFileHelper to enable saving of strings to disk
*/
bool USegmentation::FileIO__SaveStringTextToFile(
	bool useStandardMaskSaveDir,
	FString SaveDirectory,
	FString JoyfulFileName,
	FString SaveText,
	bool AllowOverWriting) {
	
	FString currGameDir = FPaths::GameDir();
	FString screenshotExtenstion = "Saved/ScreenshotMasks"; //path from GameDir to saving dir for gorund truth semantic annotation masks

	if (useStandardMaskSaveDir) {
		SaveDirectory = currGameDir + screenshotExtenstion;
		//UE_LOG(LogTemp, Warning, TEXT("currGameDir: %s"), *SaveDirectory);
	}

	//Dir Exists?
	if (!FPlatformFileManager::Get().GetPlatformFile().DirectoryExists(*SaveDirectory))
	{
		//create directory if it not exist
		FPlatformFileManager::Get().GetPlatformFile().CreateDirectory(*SaveDirectory);

		//still could not make directory?
		if (!FPlatformFileManager::Get().GetPlatformFile().DirectoryExists(*SaveDirectory))
		{
			//Could not make the specified directory
			UE_LOG(LogTemp, Warning, TEXT("Could not make the specified directory!"));
			return false;
		}
	}

	//get complete file path
	SaveDirectory += "\\";
	SaveDirectory += JoyfulFileName;

	//No over-writing?
	if (!AllowOverWriting)
	{
		//Check if file exists already
		if (FPlatformFileManager::Get().GetPlatformFile().FileExists(*SaveDirectory))
		{
			//no overwriting
			return false;
		}
	}

	return FFileHelper::SaveStringToFile(SaveText, *SaveDirectory);

}

//##########################################################################
// NORMAL DISTRIBUTION
//##########################################################################
/*
* Interfacing UEBlueprintNode to standard c libs
*/
float USegmentation::getNormalDist(float mean, float stddev) {
	std::random_device rd;
	std::mt19937 gen(rd());
	std::normal_distribution<float> normDist(mean, stddev);
	return normDist(gen);
}

//###########################################################################
// SEGMENTATION CODE
//###########################################################################
/*
* @author UE4
* Reimplementing unreals code, for "deprojectin" 2D screen coordindates to 3D worldPosition and worldDirection, to 
* make it directly accessible in this BlueprintLib
*/
bool DeprojectScreenToWorld(APlayerController const* Player, const FVector2D& ScreenPosition, FVector& WorldPosition, FVector& WorldDirection)
{
	ULocalPlayer* const LP = Player ? Player->GetLocalPlayer() : nullptr;
	if (LP && LP->ViewportClient)
	{
		// get the projection data
		FSceneViewProjectionData ProjectionData;
		if (LP->GetProjectionData(LP->ViewportClient->Viewport, eSSP_FULL, /*out*/ ProjectionData))
		{
			FMatrix const InvViewProjMatrix = ProjectionData.ComputeViewProjectionMatrix().InverseFast();
			FSceneView::DeprojectScreenToWorld(ScreenPosition, ProjectionData.GetConstrainedViewRect(), InvViewProjMatrix, /*out*/ WorldPosition, /*out*/ WorldDirection);
			return true;
		}
	}

	// something went wrong, zero things and return false
	WorldPosition = FVector::ZeroVector;
	WorldDirection = FVector::ZeroVector;
	return false;
}

/*
* Semantic segmentation function performing a ray cast for every pixel in the given camera viewport to determine underlying object.
* @return String based ground truth segmentation mask
*/
FString USegmentation::CaptureSegmentation(UObject* WorldContextObject, APlayerController const* Player, const int32 sizeX, const int32 sizeY, int32 stride, TArray<AActor*> objects, int32 nObjects, bool verbose)
{
	FString outputStringMask = "";

	UE_LOG(LogTemp, Warning, TEXT("Segmentation started..."));
	
	UWorld* World = GEngine->GetWorldFromContextObject(WorldContextObject);

	float HitResultTraceDistance = 100000.f;

	ECollisionChannel TraceChannel = ECollisionChannel::ECC_Visibility;
	bool bTraceComplex = true;
	FHitResult HitResult;


	// Iterate over each pixel in the given camera viewport
	FCollisionQueryParams CollisionQueryParams("ClickableTrace", bTraceComplex);

	if (stride == 0) {
		UE_LOG(LogTemp, Warning, TEXT("STRIDES ARE 0!!!"));

		return outputStringMask;
	}
	int32 counter = 0;

	for (int y = 0; y < sizeY; y += stride) {
		for (int x = 0; x < sizeX; x += stride) {
			FVector2D ScreenPosition(x, y);
			FVector WorldOrigin, WorldDirection;

			DeprojectScreenToWorld(Player, ScreenPosition, WorldOrigin, WorldDirection);


			// Cast ray from pixel 
			bool bHit = World->LineTraceSingleByChannel(HitResult, WorldOrigin, WorldOrigin + WorldDirection * HitResultTraceDistance, TraceChannel, CollisionQueryParams);

			AActor* Actor = NULL;
			if (bHit) {
				Actor = HitResult.GetActor();
				if (Actor != NULL) {
					bool found = false;
					for (int32 i = 0; i < nObjects; i++) {
						if (objects[i] == Actor) {
							FString IntAsString = FString::FromInt(i + 1);
							outputStringMask += IntAsString + " ";
							counter++;
							found = true;
							break;
						}
					}
					if (!found) {
						outputStringMask += "0 ";
					}
				}
				else {
					outputStringMask += "0 ";
				}
			}
			else {
				outputStringMask += "0 ";
			}
		}
		outputStringMask = outputStringMask + "\n";

	}
	UE_LOG(LogTemp, Warning, TEXT("Hit,%d"), counter);

	return outputStringMask;
}

/*
//This is an example for a Blueprint function with multiple outputs!
void USegmentation::CaptureSegmentationTwo(UObject* WorldContextObject, APlayerController const* Player, const int32 sizeX, const int32 sizeY, int32 stride, TArray<AActor*> objects, int32 nObjects, bool verbose, FString& testString, FString& hitLocation)
{
	testString = "";	//rename to outputStringMask
	hitLocation = "";

	UE_LOG(LogTemp, Warning, TEXT("Segmentation started..."));
	//FViewport* Viewport = nullptr;
	//APlayerController* PlayerController = nullptr;
	UWorld* World = GEngine->GetWorldFromContextObject(WorldContextObject);
	//FSceneView* SceneView = nullptr;

	//SceneView = GetSceneView(Player, World);


	float HitResultTraceDistance = 100000.f;

	ECollisionChannel TraceChannel = ECollisionChannel::ECC_Visibility;
	bool bTraceComplex = true;
	FHitResult HitResult;


	// Iterate over pixels
	FCollisionQueryParams CollisionQueryParams("ClickableTrace", bTraceComplex);

	if (stride == 0) {
		UE_LOG(LogTemp, Warning, TEXT("STRIDES ARE 0!!!"));

		//return testString;
		//return false;
	}
	int32 counter = 0;

	for (int y = 0; y < sizeY; y += stride) {
		for (int x = 0; x < sizeX; x += stride) {
			FVector2D ScreenPosition(x, y);
			FVector WorldOrigin, WorldDirection;

			DeprojectScreenToWorld(Player, ScreenPosition, WorldOrigin, WorldDirection);

			
			//if (y == 0 && x == 0) {
			//UE_LOG(LogTemp, Warning, TEXT("WorldDirection: %f, %f, %f; WorldOrigin: %f"),
			//WorldDirection[0], WorldDirection[1], WorldDirection[2], WorldOrigin[1]);
			//}
			

			// Cast ray from pixel to find intersecting object
			bool bHit = World->LineTraceSingleByChannel(HitResult, WorldOrigin, WorldOrigin + WorldDirection * HitResultTraceDistance, TraceChannel, CollisionQueryParams);

			AActor* Actor = NULL;
			if (bHit) {
				Actor = HitResult.GetActor();
				hitLocation += FString::SanitizeFloat(HitResult.Location.X) + " " + FString::SanitizeFloat(HitResult.Location.Y) + " ";
				if (Actor != NULL) {
					//UE_LOG(LogTemp, Warning, TEXT("Hit"));
					bool found = false;
					for (int32 i = 0; i < nObjects; i++) {
						if (objects[i] == Actor) {
							FString IntAsString = FString::FromInt(i + 1);
							testString += IntAsString + " ";
							counter++;
							found = true;
							break;
						}
					}
					if (!found) {
						testString += "0 ";
					}
				}
				else {
					testString += "0 ";
					hitLocation += "x x ";
				}
			}
			else {
				testString += "0 ";
				hitLocation += "x x ";
			}
			//testString += "0";
		}
		testString += "\n";
		hitLocation += "\n";

	}
	UE_LOG(LogTemp, Warning, TEXT("Hit,%d"), counter);

	//return testString;
}
*/

