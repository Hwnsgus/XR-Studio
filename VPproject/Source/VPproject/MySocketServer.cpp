#include "MySocketServer.h"
#include "EngineUtils.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Common/TcpSocketBuilder.h"

AMySocketServer::AMySocketServer()
{
    PrimaryActorTick.bCanEverTick = true;
}

TSharedPtr<FInternetAddr> CreateAddress(const FString& IP, int32 Port, bool& bIsValid)
{
    TSharedPtr<FInternetAddr> Addr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
    Addr->SetIp(*IP, bIsValid);
    Addr->SetPort(Port);
    return Addr;
}

void AMySocketServer::BeginPlay()
{
    Super::BeginPlay();
    ConnectToPythonServer(TEXT("127.0.0.1"), 9999);
}

void AMySocketServer::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    if (!PythonSocket || PythonSocket->GetConnectionState() != SCS_Connected)
        return;

    ReceiveAndHandleCommand();
}

// Unreal C++
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


void AMySocketServer::ReceiveAndHandleCommand()
{
    if (!PythonSocket || PythonSocket->GetConnectionState() != SCS_Connected)
        return;

    uint32 DataSize;
    if (PythonSocket->HasPendingData(DataSize))
    {
        TArray<uint8> Data;
        Data.SetNumUninitialized(DataSize);

        int32 Read = 0;
        PythonSocket->Recv(Data.GetData(), Data.Num(), Read);

        FString Command = FString(ANSI_TO_TCHAR(reinterpret_cast<const char*>(Data.GetData())));
        Command.TrimStartAndEndInline();
        Command.ReplaceInline(TEXT("\n"), TEXT(""));
        Command.ReplaceInline(TEXT("\r"), TEXT(""));
        Command.ReplaceInline(TEXT("\0"), TEXT(""));

        // ReplaceInline 다음에 추가!
        Command = Command.Replace(TEXT("\x01"), TEXT("")).Replace(TEXT("\x02"), TEXT("")).Replace(TEXT("\x03"), TEXT("")); // etc.

        for (int32 i = 0; i < Command.Len(); ++i)
        {
            if (Command[i] < 32 || Command[i] == 127) // ASCII 제어 문자 제거
            {
                Command.RemoveAt(i);
                i--; // recheck same index
            }
        }

        UE_LOG(LogTemp, Warning, TEXT("📩 명령 수신: [%s]"), *Command);

        // ✅ 여기에 Tokens 정의 추가
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
    if (!PythonSocket) return;

    FTCHARToUTF8 Convert(*Message);
    int32 Sent = 0;
    PythonSocket->Send((uint8*)Convert.Get(), Convert.Length(), Sent);

    UE_LOG(LogTemp, Warning, TEXT("📤 응답 전송: %s"), *Message);
}

void AMySocketServer::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (PythonSocket)
    {
        if (PythonSocket->GetConnectionState() == SCS_Connected)
        {
            PythonSocket->Close();
        }

        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(PythonSocket);
        PythonSocket = nullptr;
    }

    Super::EndPlay(EndPlayReason);
}