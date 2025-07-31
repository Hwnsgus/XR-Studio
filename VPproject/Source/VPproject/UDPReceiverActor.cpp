#include "UDPReceiverActor.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Networking.h"
#include "Common/UdpSocketReceiver.h"

AUDPReceiverActor::AUDPReceiverActor()
{
    PrimaryActorTick.bCanEverTick = true;
}

void AUDPReceiverActor::BeginPlay()
{
    Super::BeginPlay();
    StartUDPReceiver("UDPReceiver", "0.0.0.0", 8000); // Python과 동일 포트
}

void AUDPReceiverActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (UDPReceiver)
    {
        UDPReceiver->Stop();
        delete UDPReceiver;
        UDPReceiver = nullptr;
    }

    if (ListenSocket)
    {
        ListenSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ListenSocket);
    }

    Super::EndPlay(EndPlayReason);
}

void AUDPReceiverActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    if (TargetActor)
    {
        TargetActor->SetActorLocation(LastReceivedLocation);
    }
}

void AUDPReceiverActor::StartUDPReceiver(const FString& SocketName, const FString& IP, const int32 Port)
{
    FIPv4Address Addr;
    FIPv4Address::Parse(IP, Addr);

    TSharedRef<FInternetAddr> ListenAddr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
    ListenAddr->SetIp(Addr.Value);
    ListenAddr->SetPort(Port);

    ListenSocket = FUdpSocketBuilder(*SocketName)
        .AsNonBlocking()
        .AsReusable()
        .BoundToAddress(Addr)
        .BoundToPort(Port)
        .WithReceiveBufferSize(2 * 1024 * 1024);

    UDPReceiver = new FUdpSocketReceiver(ListenSocket, FTimespan::FromMilliseconds(100), TEXT("UDPReceiver"));
    UDPReceiver->OnDataReceived().BindUObject(this, &AUDPReceiverActor::Recv);
    UDPReceiver->Start();
}

void AUDPReceiverActor::Recv(const FArrayReaderPtr& ArrayReaderPtr, const FIPv4Endpoint& EndPt)
{
    FString Received = FString(ANSI_TO_TCHAR(reinterpret_cast<const char*>(ArrayReaderPtr->GetData())));
    TArray<FString> Parts;
    Received.ParseIntoArray(Parts, TEXT(","), true);

    if (Parts.Num() == 3)
    {
        float X = FCString::Atof(*Parts[0]);
        float Y = FCString::Atof(*Parts[1]);
        float Z = FCString::Atof(*Parts[2]);
        LastReceivedLocation = FVector(X, Y, Z);
    }
}
