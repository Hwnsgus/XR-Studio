#include "MySocketServerEditor.h"

#if WITH_EDITOR

#include "TimerManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Common/TcpSocketBuilder.h"

void AMySocketServerEditor::BeginPlay()
{
    Super::BeginPlay();

    UE_LOG(LogTemp, Warning, TEXT("🚀 BeginPlay - Editor 서버 리스닝 시도"));

    if (!ListenSocket)
    {
        StartListening(9998);
    }
    else
    {
        UE_LOG(LogTemp, Warning, TEXT("⚠️ 이미 소켓이 열려 있습니다."));
    }
}


AMySocketServerEditor::AMySocketServerEditor()
{
    PrimaryActorTick.bCanEverTick = true;

    if (!bHasInitialized)
    {
        UE_LOG(LogTemp, Warning, TEXT("✅ MySocketServerEditor 최초 생성자 호출됨"));
        bHasInitialized = true;
    }
    else
    {
        UE_LOG(LogTemp, Warning, TEXT("⚠️ 중복된 MySocketServerEditor 인스턴스가 생성됨"));
    }
}

void AMySocketServerEditor::PostInitializeComponents()
{
    Super::PostInitializeComponents();
    UE_LOG(LogTemp, Warning, TEXT("🔥 MySocketServerEditor 생성됨"));

    StartListening(9998);
}

void AMySocketServerEditor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    static float TimeSinceLastLog = 0.0f;
    TimeSinceLastLog += DeltaTime;

    if (TimeSinceLastLog >= 1.0f)
    {
        UE_LOG(LogTemp, Log, TEXT("✅ Tick 호출 중..."));
        TimeSinceLastLog = 0.0f;
    }

    if (!ClientSocket) return;

    uint32 DataSize = 0;
    if (ClientSocket->HasPendingData(DataSize))
    {
        TArray<uint8> Data;
        Data.SetNumUninitialized(DataSize);

        int32 Read = 0;
        if (ClientSocket->Recv(Data.GetData(), Data.Num(), Read) && Read > 0)
        {
            Data.Add(0); // Null terminator
            FString Command = FString(ANSI_TO_TCHAR(reinterpret_cast<const char*>(Data.GetData())));
            Command.TrimStartAndEndInline();

            UE_LOG(LogTemp, Warning, TEXT("📩 에디터 명령 수신: [%s]"), *Command);

            HandleIncomingCommand(Command);
        }
    }
}

void AMySocketServerEditor::StartListening(int32 Port)
{
    if (ListenSocket)
    {
        UE_LOG(LogTemp, Warning, TEXT("⚠️ 이미 리스닝 중입니다. (포트: %d)"), Port);
        return;
    }

    ListenSocket = FTcpSocketBuilder(TEXT("EditorSocketServer"))
        .AsReusable()
        .BoundToPort(Port)
        .Listening(8);

    if (!ListenSocket)
    {
        UE_LOG(LogTemp, Error, TEXT("❌ 에디터 ListenSocket 생성 실패 (포트: %d)"), Port);
        return;
    }

    UE_LOG(LogTemp, Warning, TEXT("✅ 에디터 소켓 리슨 시작됨 (포트: %d)"), Port);

    UWorld* World = GetWorld();
    if (World)
    {
        World->GetTimerManager().SetTimer(ListenTimerHandle, this, &AMySocketServerEditor::AcceptClients, 0.2f, true);
    }
    else
    {
        UE_LOG(LogTemp, Error, TEXT("❌ World가 유효하지 않아 타이머 설정 실패"));
    }
}

void AMySocketServerEditor::AcceptClients()
{
    if (!ListenSocket) return;

    TSharedRef<FInternetAddr> ClientAddr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();

    bool Pending;
    if (ListenSocket->HasPendingConnection(Pending) && Pending)
    {
        UE_LOG(LogTemp, Log, TEXT("⏳ 연결 대기 중..."));

        FSocket* NewClient = ListenSocket->Accept(*ClientAddr, TEXT("EditorClient"));
        if (NewClient)
        {
            ClientSocket = NewClient;
            UE_LOG(LogTemp, Log, TEXT("✅ Editor 클라이언트 접속됨: %s"), *ClientAddr->ToString(true));
        }
    }
}

void AMySocketServerEditor::HandleIncomingCommand(const FString& Command)
{
    if (Command.StartsWith("SPAWN_ASSET"))
    {
        FString AssetPath = Command.RightChop(11).TrimQuotes().TrimStartAndEnd();

        if (UStaticMesh* StaticMesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, *AssetPath)))
        {
            UWorld* World = GEditor->GetEditorWorldContext().World();
            if (!World)
            {
                UE_LOG(LogTemp, Error, TEXT("❌ 에디터 월드 없음"));
                return;
            }

            AStaticMeshActor* MeshActor = World->SpawnActor<AStaticMeshActor>(
                AStaticMeshActor::StaticClass(),
                FVector(0, 0, 100),
                FRotator::ZeroRotator
            );

            if (MeshActor && MeshActor->GetStaticMeshComponent())
            {
                MeshActor->GetStaticMeshComponent()->SetStaticMesh(StaticMesh);
                MeshActor->SetActorLabel(TEXT("Spawned_StaticMesh"));
                UE_LOG(LogTemp, Log, TEXT("✅ Spawned actor: %s"), *MeshActor->GetName());
            }
            else
            {
                UE_LOG(LogTemp, Error, TEXT("❌ StaticMeshActor 생성 실패 또는 컴포넌트 없음"));
            }
        }
        else
        {
            UE_LOG(LogTemp, Warning, TEXT("❌ StaticMesh 로드 실패: %s"), *AssetPath);
        }

        return;
    }

    if (Command.StartsWith("py "))
    {
        FString ScriptAndArgs = Command.Mid(3).TrimStartAndEnd();
        if (!ScriptAndArgs.IsEmpty())
        {
            ExecutePythonAfterDelay(ScriptAndArgs);
        }
        else
        {
            UE_LOG(LogTemp, Warning, TEXT("⚠️ py 명령에 인자가 없습니다."));
        }

        return;
    }

    if (Command.StartsWith("IMPORT_FBX"))
    {
        FString FBXPath = Command.RightChop(11).TrimQuotes().TrimStartAndEnd();

        if (!FPaths::FileExists(FBXPath))
        {
            UE_LOG(LogTemp, Error, TEXT("❌ 파일 없음: %s"), *FBXPath);
            return;
        }

        FString Script;
        Script += "import unreal\n";
        Script += "import os\n";
        Script += FString::Printf(TEXT("fbx_path = r\"%s\"\n"), *FBXPath);
        Script += "asset_tools = unreal.AssetToolsHelpers.get_asset_tools()\n";
        Script += "destination_path = '/Game/Imported'\n";
        Script += "filename = os.path.splitext(os.path.basename(fbx_path))[0]\n";
        Script += "task = unreal.AssetImportTask()\n";
        Script += "task.filename = fbx_path\n";
        Script += "task.destination_path = destination_path\n";
        Script += "task.automated = True\n";
        Script += "task.save = True\n";
        Script += "asset_tools.import_asset_tasks([task])\n";
        Script += "mesh_path = destination_path + '/' + filename\n";
        Script += "mesh = unreal.load_asset(mesh_path)\n";
        Script += "if mesh:\n";
        Script += "    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(mesh, unreal.Vector(0,0,100), unreal.Rotator(0,0,0))\n";
        Script += "    print('✅ Spawned:', actor.get_name())\n";
        Script += "else:\n";
        Script += "    print('❌ Failed to import mesh')\n";

        FString TempScriptPath = TEXT("D:/git/XR-Studio/MyProjectCamera/Content/Python/TempFbxImportScript.py");
        FFileHelper::SaveStringToFile(Script, *TempScriptPath);

        ExecutePythonAfterDelay(TempScriptPath);
        return;
    }

    UE_LOG(LogTemp, Warning, TEXT("⚠️ 알 수 없는 명령 (에디터 전용): %s"), *Command);
}

void AMySocketServerEditor::ExecutePythonAfterDelay(const FString& PyCommand)
{
    FTimerHandle TimerHandle;
    GetWorld()->GetTimerManager().SetTimer(TimerHandle, [PyCommand]()
        {
            if (GEditor)
            {
                GEditor->Exec(nullptr, *FString::Printf(TEXT("py %s"), *PyCommand));
                UE_LOG(LogTemp, Log, TEXT("🟢 Python 스크립트 실행됨: %s"), *PyCommand);
            }
            else
            {
                UE_LOG(LogTemp, Error, TEXT("❌ GEditor 사용 불가"));
            }
        }, 0.1f, false);
}

void AMySocketServerEditor::EndPlay(const EEndPlayReason::Type EndPlayReason)
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

#endif // WITH_EDITOR
