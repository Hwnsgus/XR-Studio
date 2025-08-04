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


void AMyCameraController::BeginPlay()
{
    Super::BeginPlay();

    if (CineCamera)
    {
        FVector CamLoc = CineCamera->GetComponentLocation();
        UE_LOG(LogTemp, Warning, TEXT("📷 Camera Location: X=%.1f, Y=%.1f, Z=%.1f"), CamLoc.X, CamLoc.Y, CamLoc.Z);
    }

    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        AActor* Actor = *It;
        if (Actor && Actor->GetName().Contains("Cube"))
        {
            FVector ActorLoc = Actor->GetActorLocation();
            UE_LOG(LogTemp, Warning, TEXT("🟦 Cube Location: X=%.1f, Y=%.1f, Z=%.1f"), ActorLoc.X, ActorLoc.Y, ActorLoc.Z);
        }
    }

    UE_LOG(LogTemp, Warning, TEXT("💡 콘솔에서 명령어 사용: SetActorLocationByName [ActorName] [X] [Y] [Z]"));

}

void AMyCameraController::SetActorLocationByName(FString ActorName, float X, float Y, float Z)
{
    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        FString FoundName = It->GetName();
        UE_LOG(LogTemp, Warning, TEXT("📌 Found Actor: %s"), *FoundName);

        if (FoundName.Contains(ActorName))
        {
            It->SetActorLocation(FVector(X, Y, Z));
            UE_LOG(LogTemp, Warning, TEXT("✅ %s 이동 완료 → (%.1f, %.1f, %.1f)"), *ActorName, X, Y, Z);
            return;
        }
    }

    UE_LOG(LogTemp, Error, TEXT("❌ %s 이름의 액터를 찾을 수 없음"), *ActorName);
}