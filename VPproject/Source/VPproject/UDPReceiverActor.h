#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UDPReceiverActor.generated.h"

UCLASS()
class VPRODPROJECT_API AUDPReceiverActor : public AActor
{
    GENERATED_BODY()

public:
    AUDPReceiverActor();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

public:
    virtual void Tick(float DeltaTime) override;

private:
    FSocket* ListenSocket;
    FUdpSocketReceiver* UDPReceiver;

    void StartUDPReceiver(const FString& SocketName, const FString& IP, const int32 Port);
    void Recv(const FArrayReaderPtr& ArrayReaderPtr, const FIPv4Endpoint& EndPt);

    UPROPERTY(EditAnywhere, Category = "UDP")
    AActor* TargetActor;

    FVector LastReceivedLocation;
};
