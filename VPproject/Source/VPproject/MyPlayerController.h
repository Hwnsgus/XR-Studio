// MyPlayerController.h

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "MyPlayerController.generated.h"

UCLASS()
class MYPROJECTCAMERA_API AMyPlayerController : public APlayerController
{
    GENERATED_BODY()

public:
    UFUNCTION(Exec)
    void SetActorLocationByName(const FString& ActorName, float X, float Y, float Z);
};
