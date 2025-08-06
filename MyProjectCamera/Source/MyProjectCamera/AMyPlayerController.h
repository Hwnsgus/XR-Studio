#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "AMyPlayerController.generated.h"

UCLASS()
class MYPROJECTCAMERA_API AMyPlayerController : public APlayerController
{
    GENERATED_BODY()

public:
    AMyPlayerController();

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
};
