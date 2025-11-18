#include "AMyPlayerController.h"

AMyPlayerController::AMyPlayerController()
{
    PrimaryActorTick.bCanEverTick = true;
}

void AMyPlayerController::BeginPlay()
{
    Super::BeginPlay();
}

void AMyPlayerController::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
}
