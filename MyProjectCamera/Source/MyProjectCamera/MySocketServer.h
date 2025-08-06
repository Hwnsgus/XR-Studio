#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "MySocketServer.generated.h"

UCLASS()
class MYPROJECTCAMERA_API AMySocketServer : public AActor
{
    GENERATED_BODY()

public:
    AMySocketServer();

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

   // void ConnectToPythonServer(const FString& IP, int32 Port);
   // void ReceiveAndHandleCommand();
    void StartListening(int32 Port);
    void AcceptClients();
    FString HandleCommand(const FString& Command);
    void SendResponseToPython(const FString& Message);
    FString GetAllActorNames();


private:
    FSocket* ListenSocket = nullptr;
    FSocket* ClientSocket = nullptr;
    FTimerHandle ListenTimerHandle;
    TSharedPtr<FInternetAddr> PythonAddress;

#if WITH_EDITOR
    void ExecutePythonAfterDelay(const FString& ScriptPath);
    FString HandleImportFbx(const FString& Command);
#endif

};
