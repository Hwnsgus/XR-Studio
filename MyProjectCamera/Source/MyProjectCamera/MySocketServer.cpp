#include "MySocketServer.h"
#include "EngineUtils.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Common/TcpSocketBuilder.h"

#include "MySocketServer.h"
#include "EngineUtils.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Common/TcpSocketBuilder.h"

AMySocketServer::AMySocketServer()
{
    PrimaryActorTick.bCanEverTick = true;
}

void AMySocketServer::BeginPlay()
{
    Super::BeginPlay();
    StartListening(9999); // ✅ 서버 시작
}

void AMySocketServer::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    if (!ClientSocket)
    {
        UE_LOG(LogTemp, Error, TEXT("❌ ClientSocket is NULL"));
        return;
    }

    if (ClientSocket->GetConnectionState() != SCS_Connected)
    {
        UE_LOG(LogTemp, Warning, TEXT("🔌 ClientSocket disconnected"));
        return;
    }


    uint32 DataSize = 0;
    if (ClientSocket->HasPendingData(DataSize))
    {
        TArray<uint8> Data;
        Data.SetNumUninitialized(DataSize);

        int32 Read = 0;
        bool bReceived = ClientSocket->Recv(Data.GetData(), Data.Num(), Read);

        if (!bReceived || Read <= 0)
        {
            UE_LOG(LogTemp, Error, TEXT("❌ 데이터 수신 실패 또는 데이터 없음 (Read: %d)"), Read);
            return;
        }

        // 수신된 데이터를 안전하게 문자열로 변환
        const char* CharData = reinterpret_cast<const char*>(Data.GetData());
        FString Command = FString(ANSI_TO_TCHAR(CharData));



        FString Command = FString(ANSI_TO_TCHAR(reinterpret_cast<const char*>(Data.GetData())));
        Command.TrimStartAndEndInline();
        Command.ReplaceInline(TEXT("\n"), TEXT(""));
        Command.ReplaceInline(TEXT("\r"), TEXT(""));
        Command.ReplaceInline(TEXT("\0"), TEXT(""));
        Command = Command.Replace(TEXT("\x01"), TEXT("")).Replace(TEXT("\x02"), TEXT("")).Replace(TEXT("\x03"), TEXT(""));

        for (int32 i = 0; i < Command.Len(); ++i)
        {
            if (Command[i] < 32 || Command[i] == 127)
            {
                Command.RemoveAt(i);
                i--;
            }
        }

        UE_LOG(LogTemp, Warning, TEXT("📩 명령 수신: [%s]"), *Command);

        TArray<FString> Tokens;
        Command.ParseIntoArrayWS(Tokens);

        if (Tokens.Num() >= 1 && Tokens[0].Equals(TEXT("LIST"), ESearchCase::IgnoreCase))
        {
            FString ActorNames = GetAllActorNames();
            SendResponseToPython(ActorNames);
            return;
        }

        FString Result = HandleCommand(Command);
        SendResponseToPython(Result);
    }
}

void AMySocketServer::StartListening(int32 Port)
{
    ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    ListenSocket = FTcpSocketBuilder(TEXT("UnrealSocketServer"))
        .AsReusable()
        .BoundToPort(Port)
        .Listening(8);

    if (!ListenSocket)
    {
        UE_LOG(LogTemp, Error, TEXT("❌ 서버 소켓 생성 실패"));
        return;
    }

    UE_LOG(LogTemp, Log, TEXT("✅ Unreal TCP 서버 시작됨 (Port: %d)"), Port);

    GetWorld()->GetTimerManager().SetTimer(ListenTimerHandle, this, &AMySocketServer::AcceptClients, 0.1f, true);
}

void AMySocketServer::AcceptClients()
{
    bool bHasPending;
    if (ListenSocket->HasPendingConnection(bHasPending) && bHasPending)
    {
        TSharedRef<FInternetAddr> RemoteAddress = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
        ClientSocket = ListenSocket->Accept(*RemoteAddress, TEXT("PythonClient"));

        if (ClientSocket)
        {
            UE_LOG(LogTemp, Warning, TEXT("✅ Python 클라이언트 접속: %s"), *RemoteAddress->ToString(true));
        }
    }
}

FString AMySocketServer::HandleCommand(const FString& Command)
{
    TArray<FString> Tokens;
    Command.ParseIntoArrayWS(Tokens);

    if (Tokens.Num() >= 5 && Tokens[0] == "MOVE")
    {
        FString ActorName = Tokens[1];
        float X = FCString::Atof(*Tokens[2]);
        float Y = FCString::Atof(*Tokens[3]);
        float Z = FCString::Atof(*Tokens[4]);

        for (TActorIterator<AActor> It(GetWorld()); It; ++It)
        {
            if (It->GetName().Equals(ActorName, ESearchCase::IgnoreCase))
            {
                It->SetActorLocation(FVector(X, Y, Z));
                return FString::Printf(TEXT("✅ %s 이동 완료: (%.1f, %.1f, %.1f)"), *ActorName, X, Y, Z);
            }
        }

        return FString::Printf(TEXT("❌ '%s' 이름의 액터를 찾을 수 없음"), *ActorName);
    }

    return TEXT("❌ 알 수 없는 명령");
}

FString AMySocketServer::GetAllActorNames()
{
    FString Result;

    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        FString Name = It->GetName();
        UE_LOG(LogTemp, Warning, TEXT("📌 Actor: %s"), *Name);
        Result += Name + LINE_TERMINATOR;
    }

    return Result;
}

void AMySocketServer::SendResponseToPython(const FString& Message)
{
    if (!ClientSocket) return;

    FTCHARToUTF8 Convert(*Message);
    int32 Sent = 0;
    ClientSocket->Send((uint8*)Convert.Get(), Convert.Length(), Sent);

    UE_LOG(LogTemp, Log, TEXT("📤 응답 전송: %s"), *Message);
}

void AMySocketServer::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (ClientSocket)
    {
        ClientSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ClientSocket);
        ClientSocket = nullptr;
    }

    if (ListenSocket)
    {
        ListenSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ListenSocket);
        ListenSocket = nullptr;
    }

    Super::EndPlay(EndPlayReason);
}


/*
// Unreal -> Python 연결 예제
void AMySocketServer::ConnectToPythonServer(const FString& IP, int32 Port)
{
    bool bIsValid;
    PythonAddress = CreateAddress(IP, Port, bIsValid);

    if (!bIsValid)
    {
        UE_LOG(LogTemp, Error, TEXT("❌ 잘못된 IP 주소입니다."));
        return;
    }

    PythonSocket = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)
        ->CreateSocket(NAME_Stream, TEXT("PythonClient"), false);

    int32 RetryCount = 0;
    const int32 MaxRetries = 10;

    while (!PythonSocket->Connect(*PythonAddress) && RetryCount < MaxRetries)
    {
        UE_LOG(LogTemp, Warning, TEXT("🔁 Python 서버 재시도 중... (%d)"), RetryCount + 1);
        FPlatformProcess::Sleep(1.0f); // 1초 대기
        RetryCount++;
    }

    if (RetryCount >= MaxRetries)
    {
        UE_LOG(LogTemp, Error, TEXT("❌ Python 서버 연결 실패"));
        return;
    }

    UE_LOG(LogTemp, Warning, TEXT("✅ Python 서버 연결 성공"));

}

void AMySocketServer::SendResponseToPython(const FString& Message)
{
    if (!PythonSocket) return;

    FTCHARToUTF8 Convert(*Message);
    int32 Sent = 0;
    PythonSocket->Send((uint8*)Convert.Get(), Convert.Length(), Sent);

    UE_LOG(LogTemp, Warning, TEXT("📤 응답 전송: %s"), *Message);
}


*/