#include "MyEditorSocketSubsystem.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Common/TcpSocketBuilder.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"

#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"   // ✅ 꼭 필요
#include "EditorSubsystem.h"   // (선택) 에디터 관련
#include "Containers/Ticker.h"        // ✅ FTSTicker 사용 시

#define UE_LOG_TAG LogTemp

void UMyEditorSocketSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
#if WITH_EDITOR
    UE_LOG(UE_LOG_TAG, Warning, TEXT("🔧 UMyEditorSocketSubsystem Initialize"));
    StartListening(9998);

    // 100ms 간격으로 Accept + Recv 폴링 (에디터 어디서든 동작)
    TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateLambda([this](float)->bool
            {
                AcceptClients();
                PumpClient();
                return true; // 계속
            }), 0.1f);
#endif
}

void UMyEditorSocketSubsystem::Deinitialize()
{
#if WITH_EDITOR
    UE_LOG(UE_LOG_TAG, Warning, TEXT("🔧 UMyEditorSocketSubsystem Deinitialize"));
    if (TickerHandle.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
        TickerHandle.Reset();
    }
    StopListening();
#endif
}

void UMyEditorSocketSubsystem::StartListening(int32 Port)
{
    if (ListenSocket) return;

    ListenSocket = FTcpSocketBuilder(TEXT("EditorSocketServer"))
        .AsReusable()
        .BoundToPort(Port)
        .Listening(8);

    if (!ListenSocket)
    {
        UE_LOG(UE_LOG_TAG, Error, TEXT("❌ ListenSocket 생성 실패 (포트 %d)"), Port);
        return;
    }
    UE_LOG(UE_LOG_TAG, Warning, TEXT("✅ 에디터 소켓 리슨 시작 (포트 %d)"), Port);
}

void UMyEditorSocketSubsystem::StopListening()
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
}

void UMyEditorSocketSubsystem::AcceptClients()
{
    if (!ListenSocket) return;

    bool bPending = false;
    if (!ListenSocket->HasPendingConnection(bPending))
        return;

    if (!bPending) return;

    TSharedRef<FInternetAddr> ClientAddr =
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();

    FSocket* NewClient = ListenSocket->Accept(*ClientAddr, TEXT("EditorClient"));
    if (NewClient)
    {
        if (ClientSocket)
        {
            ClientSocket->Close();
            ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ClientSocket);
        }
        ClientSocket = NewClient;
        UE_LOG(UE_LOG_TAG, Log, TEXT("✅ Editor 클라이언트 접속: %s"), *ClientAddr->ToString(true));
    }
}

void UMyEditorSocketSubsystem::PumpClient()
{
    if (!ClientSocket) return;

    uint32 DataSize = 0;
    if (!ClientSocket->HasPendingData(DataSize) || DataSize == 0)
        return;

    TArray<uint8> Data;
    Data.SetNumUninitialized(DataSize);

    int32 Read = 0;
    if (ClientSocket->Recv(Data.GetData(), Data.Num(), Read) && Read > 0)
    {
        Data.Add(0);
        FString Command = FString(ANSI_TO_TCHAR(reinterpret_cast<const char*>(Data.GetData())));
        Command.TrimStartAndEndInline();
        UE_LOG(UE_LOG_TAG, Warning, TEXT("📩 에디터 명령 수신: [%s]"), *Command);
        HandleIncomingCommand(Command);
    }
}

bool UMyEditorSocketSubsystem::IsPIEActive() const
{
    return GEditor && GEditor->PlayWorld != nullptr;
}

void UMyEditorSocketSubsystem::HandleIncomingCommand(const FString& Command)
{
    // 에디터 전용 가드 (PIE 차단)
    if (IsPIEActive())
    {
        UE_LOG(UE_LOG_TAG, Error, TEXT("🚫 PIE 상태에서는 에디터 명령 처리 불가"));
        return;
    }

    // 1) C++ 직스폰 (기존 AActor 코드와 동일 동작)
    if (Command.StartsWith(TEXT("SPAWN_ASSET")))
    {
        const FString AssetPath = Command.RightChop(11).TrimQuotes().TrimStartAndEnd();

        if (UStaticMesh* StaticMesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, *AssetPath)))
        {
            UWorld* EditorWorld = GEditor->GetEditorWorldContext().World();
            if (!EditorWorld)
            {
                UE_LOG(UE_LOG_TAG, Error, TEXT("❌ EditorWorld 없음"));
                return;
            }

            AStaticMeshActor* MeshActor = EditorWorld->SpawnActor<AStaticMeshActor>(
                AStaticMeshActor::StaticClass(),
                FVector(0, 0, 100),
                FRotator::ZeroRotator
            );
            if (MeshActor && MeshActor->GetStaticMeshComponent())
            {
                MeshActor->GetStaticMeshComponent()->SetStaticMesh(StaticMesh);
                MeshActor->SetActorLabel(TEXT("Spawned_StaticMesh"));
                UE_LOG(UE_LOG_TAG, Log, TEXT("✅ Spawned: %s"), *MeshActor->GetName());
            }
            else
            {
                UE_LOG(UE_LOG_TAG, Error, TEXT("❌ StaticMeshActor 생성 실패/컴포넌트 없음"));
            }
            return;
        }
        UE_LOG(UE_LOG_TAG, Warning, TEXT("❌ StaticMesh 로드 실패: %s"), *AssetPath);
        return;
    }

    // 2) 에디터 파이썬 실행 (editor_spawn_actor.py 호출 루트)
    if (Command.StartsWith(TEXT("py ")))
    {
        const FString ScriptAndArgs = Command.Mid(3).TrimStartAndEnd();
        if (!ScriptAndArgs.IsEmpty())
        {
            ExecPython(ScriptAndArgs);
        }
        else
        {
            UE_LOG(UE_LOG_TAG, Warning, TEXT("⚠️ py 명령 인자 없음"));
        }
        return;
    }

    UE_LOG(UE_LOG_TAG, Warning, TEXT("⚠️ 알 수 없는 명령: %s"), *Command);
}

void UMyEditorSocketSubsystem::ExecPython(const FString& PyCommand)
{
    if (!GEditor) { UE_LOG(UE_LOG_TAG, Error, TEXT("❌ GEditor 없음")); return; }

    // Editor 콘솔로 넘김:  ex) py "D:/.../editor_spawn_actor.py" --asset "/Game/..." --spawn
    const FString Full = FString::Printf(TEXT("py %s"), *PyCommand);
    GEditor->Exec(nullptr, *Full);
    UE_LOG(UE_LOG_TAG, Log, TEXT("🟢 Python 실행: %s"), *PyCommand);
}
