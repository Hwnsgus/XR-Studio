// MyPlayerController.cpp

#include "MyPlayerController.h"
#include "Engine/World.h"
#include "EngineUtils.h"

void AMyPlayerController::SetActorLocationByName(const FString& ActorName, float X, float Y, float Z)
{
    if (!GetWorld())
    {
        UE_LOG(LogTemp, Error, TEXT("🌍 월드를 찾을 수 없습니다."));
        return;
    }

    bool bFound = false;

    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        FString FoundName = It->GetName();
        UE_LOG(LogTemp, Warning, TEXT("📌 Found Actor: %s"), *FoundName);

        if (FoundName.Contains(ActorName))
        {
            It->SetActorLocation(FVector(X, Y, Z));
            UE_LOG(LogTemp, Warning, TEXT("✅ %s 이동 완료 → (%.1f, %.1f, %.1f)"), *FoundName, X, Y, Z);
            bFound = true;
            break;
        }
    }

    if (!bFound)
    {
        UE_LOG(LogTemp, Error, TEXT("❌ '%s' 이름을 포함하는 액터를 찾을 수 없습니다."), *ActorName);
    }
}
