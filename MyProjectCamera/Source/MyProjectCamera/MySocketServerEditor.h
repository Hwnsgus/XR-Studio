#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Sockets.h"
#include "SocketSubsystem.h"

#include "MySocketServerEditor.generated.h" 

UCLASS()
class MYPROJECTCAMERA_API AMySocketServerEditor : public AActor
{
    GENERATED_BODY()

public:
    AMySocketServerEditor();

#if WITH_EDITOR
    virtual void BeginPlay() override;
    virtual void PostInitializeComponents() override;
    virtual bool ShouldTickIfViewportsOnly() const override { return true; }
    virtual void Tick(float DeltaTime) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    void StartListening(int32 Port);
    void AcceptClients();
    void HandleIncomingCommand(const FString& Command);
    void ExecutePythonAfterDelay(const FString& ScriptPath);

    FSocket* ListenSocket = nullptr;
    FSocket* ClientSocket = nullptr;
    FTimerHandle ListenTimerHandle;
    static bool bHasInitialized;
#endif
};
