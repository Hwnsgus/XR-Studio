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

void AMyCameraController::BeginPlay()
{
    Super::BeginPlay();

    // 필요 시 초기화 로직 작성
    UE_LOG(LogTemp, Warning, TEXT("📸 AMyCameraController::BeginPlay 호출됨"));
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

void AMyCameraController::SetActorLocationByName(FString ActorName, float X, float Y, float Z)
{
    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        if (It->GetName().Equals(ActorName, ESearchCase::IgnoreCase))
        {
            It->SetActorLocation(FVector(X, Y, Z));
            UE_LOG(LogTemp, Log, TEXT("📦 액터 [%s] 위치 설정: %.1f, %.1f, %.1f"), *ActorName, X, Y, Z);
            return;
        }
    }

    UE_LOG(LogTemp, Warning, TEXT("❌ '%s' 이름의 액터를 찾을 수 없음"), *ActorName);
}
