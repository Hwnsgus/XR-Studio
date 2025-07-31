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

    void ConnectToPythonServer(const FString& IP, int32 Port);
    void ReceiveAndHandleCommand();
    FString HandleCommand(const FString& Command);
    void SendResponseToPython(const FString& Message);
    FString GetAllActorNames();

private:
    FSocket* PythonSocket = nullptr;
    TSharedPtr<FInternetAddr> PythonAddress;
};
