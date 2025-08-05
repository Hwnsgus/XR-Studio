// Fill out your copyright notice in the Description page of Project Settings.


#include "MyCameraController.h"
#include "EngineUtils.h"

AMyCameraController::AMyCameraController()
{
    PrimaryActorTick.bCanEverTick = true;

    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("RootComponent"));

    CineCamera = CreateDefaultSubobject<UCineCameraComponent>(TEXT("CineCamera"));
    CineCamera->SetupAttachment(RootComponent);
}

void AMyCameraController::OnConstruction(const FTransform& Transform)
{
    SetActorLocation(ActorTargetLocation);

    if (CineCamera)
    {
        CineCamera->SetRelativeLocation(CameraTargetLocation);
    }
}

void AMyCameraController::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    if (TargetActor)
    {
        FVector TargetLocation = TargetActor->GetActorLocation();
        SetActorLocation(TargetLocation);
    }
}


    }
