// MyCameraController.h
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MyCameraController.generated.h"

// ✅ 전방 선언(포인터에만 필요). 반드시 UCLASS 전에 위치.
class UCineCameraComponent;
class USceneComponent;

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

    UPROPERTY(EditAnywhere, Category = "Tracking")
    AActor* TargetActor = nullptr;

    UPROPERTY(EditAnywhere, Category = "Location Control")
    FVector ActorTargetLocation = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, Category = "Location Control")
    FVector CameraTargetLocation = FVector::ZeroVector;

    // ✅ 전방선언한 타입의 포인터는 헤더에 OK
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
    UCineCameraComponent* CineCamera = nullptr;
};
