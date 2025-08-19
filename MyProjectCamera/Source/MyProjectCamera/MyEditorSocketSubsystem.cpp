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
#include "AssetRegistry/AssetRegistryModule.h"  // UAssetRegistryHelpers, FAssetData
#include "AssetRegistry/IAssetRegistry.h"       // IAssetRegistry 인터페이스
#include "UObject/SoftObjectPath.h"             // FSoftObjectPath

#define UE_LOG_TAG LogTemp

void UMyEditorSocketSubsystem::SendToClient(const FString& Text)
{
    if (!ClientSocket) return;
    FTCHARToUTF8 Conv(*Text);
    int32 Sent = 0;
    ClientSocket->Send((uint8*)Conv.Get(), Conv.Length(), Sent);
}


void UMyEditorSocketSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    FEditorDelegates::BeginPIE.AddUObject(this, &UMyEditorSocketSubsystem::OnBeginPIE);
    FEditorDelegates::EndPIE.AddUObject(this, &UMyEditorSocketSubsystem::OnEndPIE);
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

void UMyEditorSocketSubsystem::OnBeginPIE(const bool /*bIsSimulating*/)
{
    // 9998에 붙어 있던 클라에게 전환 지시 후 연결 끊기
    SendToClient(TEXT("SWITCH:PIE\n"));
    if (ClientSocket)
    {
        ClientSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ClientSocket);
        ClientSocket = nullptr;
    }
}

void UMyEditorSocketSubsystem::OnEndPIE(const bool /*bIsSimulating*/)
{
    // 에디터 모드 복귀 알림 (연결이 이미 끊어졌을 수 있으니 best-effort)
    SendToClient(TEXT("SWITCH:EDITOR\n"));
    // 9998 리슨은 계속 유지 중이니 추가 처리 불필요
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

static UObject* LoadAnyObjectByPath(const FString& InPath)
{
    FString Path = InPath;

    // "/Game/Foo/Bar" → "/Game/Foo/Bar.Bar" 자동 보정
    if (!Path.Contains(TEXT(".")))
    {
        const FString Short = FPackageName::GetShortName(Path);
        Path += TEXT(".") + Short;
    }

    // 1) 직접 로드
    if (UObject* Obj = StaticLoadObject(UObject::StaticClass(), nullptr, *Path))
        return Obj;

    // 2) 에셋 레지스트리 (모듈 통해 가져오기)
    FAssetRegistryModule& ARM = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    IAssetRegistry& Registry = ARM.Get();

    const FSoftObjectPath SoftPath(Path);
    FAssetData Data = Registry.GetAssetByObjectPath(SoftPath, /*bIncludeOnlyOnDiskAssets*/ false);
    if (Data.IsValid())
    {
        return Data.GetAsset();
    }

    return nullptr;
}

void UMyEditorSocketSubsystem::HandleIncomingCommand(const FString& Command)
{
    // 에디터 전용 가드 (PIE 차단)
    if (IsPIEActive())
    {
        UE_LOG(UE_LOG_TAG, Error, TEXT("🚫 PIE 상태에서는 에디터 명령 처리 불가"));
        SendToClient(TEXT("ERR PIE\n"));
        return;
    }

    if (Command.StartsWith(TEXT("SPAWN_ASSET")))
    {
        auto CleanArg = [](FString S)
            {
                S.ReplaceInline(TEXT("\r"), TEXT(""));
                S.ReplaceInline(TEXT("\n"), TEXT(""));
                S.TrimStartAndEndInline();

                if (S.StartsWith(TEXT("\"")) && S.EndsWith(TEXT("\"")))
                {
                    S = S.Mid(1, S.Len() - 2);
                }
                else if (S.StartsWith(TEXT("'")) && S.EndsWith(TEXT("'")))
                {
                    S = S.Mid(1, S.Len() - 2);
                }
                S.TrimStartAndEndInline();
                return S;
            };

        const int32 PrefixLen = 12; // "SPAWN_ASSET " (뒤 공백 포함)
        const FString AssetPath = CleanArg(Command.Mid(PrefixLen));

        UObject* Obj = LoadAnyObjectByPath(AssetPath);          // ← 점 없는 경로 자동보정 포함
        UStaticMesh* StaticMesh = Cast<UStaticMesh>(Obj);

        if (!StaticMesh)
        {
            UE_LOG(UE_LOG_TAG, Warning, TEXT("❌ StaticMesh 로드 실패: %s"), *AssetPath);
            SendToClient(TEXT("ERR LoadFailed\n"));
            return;
        }

        UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
        if (!EditorWorld)
        {
            UE_LOG(UE_LOG_TAG, Error, TEXT("❌ EditorWorld 없음"));
            SendToClient(TEXT("ERR NoWorld\n"));
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
            SendToClient(TEXT("OK Spawned\n"));
            return;
        }

        UE_LOG(UE_LOG_TAG, Error, TEXT("❌ StaticMeshActor 생성 실패/컴포넌트 없음"));
        SendToClient(TEXT("ERR SpawnFailed\n"));
        return;
    }

    if (Command.StartsWith(TEXT("py ")))
    {
        const FString ScriptAndArgs = Command.Mid(3).TrimStartAndEnd();
        if (!ScriptAndArgs.IsEmpty())
        {
            ExecPython(ScriptAndArgs);
            SendToClient(TEXT("OK Py\n"));
        }
        else
        {
            UE_LOG(UE_LOG_TAG, Warning, TEXT("⚠️ py 명령 인자 없음"));
            SendToClient(TEXT("ERR PyArgs\n"));
        }
        return;
    }

    UE_LOG(UE_LOG_TAG, Warning, TEXT("⚠️ 알 수 없는 명령: %s"), *Command);
    SendToClient(TEXT("ERR Unknown\n"));
}


void UMyEditorSocketSubsystem::ExecPython(const FString& PyCommand)
{
    if (!GEditor) { UE_LOG(UE_LOG_TAG, Error, TEXT("❌ GEditor 없음")); return; }

    // Editor 콘솔로 넘김:  ex) py "D:/.../editor_spawn_actor.py" --asset "/Game/..." --spawn
    const FString Full = FString::Printf(TEXT("py %s"), *PyCommand);
    GEditor->Exec(nullptr, *Full);
    UE_LOG(UE_LOG_TAG, Log, TEXT("🟢 Python 실행: %s"), *PyCommand);
}
