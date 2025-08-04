// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CineCameraComponent.h"
#include "MyCameraController.generated.h"

UCLASS()
class MYPROJECTCAMERA_API AMyCameraController : public AActor
{
    GENERATED_BODY()

public:
    AMyCameraController();

protected:
    virtual void BeginPlay() override;
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void Tick(float DeltaTime) override;


public:
    UFUNCTION(Exec)
    void SetActorLocationByName(FString ActorName, float X, float Y, float Z);

    // 추적할 액터
    UPROPERTY(EditAnywhere, Category = "Tracking")
    AActor* TargetActor;


    // 액터의 위치 (자기 자신)
    UPROPERTY(EditAnywhere, Category = "Location Control")
    FVector ActorTargetLocation;

    // 카메라 컴포넌트의 로컬 위치
    UPROPERTY(EditAnywhere, Category = "Location Control")
    FVector CameraTargetLocation;

    // 시네 카메라 컴포넌트
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
    UCineCameraComponent* CineCamera;

    UFUNCTION(Exec)
    void PrintCameraLocation()
    {
        if (CineCamera)
        {
            FVector CamLoc = CineCamera->GetComponentLocation();
            UE_LOG(LogTemp, Warning, TEXT("카메라 현재 위치: X=%.1f, Y=%.1f, Z=%.1f"), CamLoc.X, CamLoc.Y, CamLoc.Z);
        }
    }
};
