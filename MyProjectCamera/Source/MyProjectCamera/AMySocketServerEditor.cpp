#include "AMySocketServerEditor.h"

#if WITH_EDITOR

#include "TimerManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Common/TcpSocketBuilder.h"

AMySocketServerEditor::AMySocketServerEditor()
{
    PrimaryActorTick.bCanEverTick = true;
}

void AMySocketServerEditor::PostInitializeComponents()
{
    Super::PostInitializeComponents();
    if (!IsRunningCommandlet() && GEditor)
    {
        StartListening(9998); // 🎯 에디터 전용 포트
        UE_LOG(LogTemp, Log, TEXT("✅ AMySocketServerEditor 초기화 완료"));
    }
}

void AMySocketServerEditor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

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
    ListenSocket = FTcpSocketBuilder(TEXT("EditorSocketServer"))
        .AsReusable()
        .BoundToPort(Port)
        .Listening(8);

    if (!ListenSocket)
    {
        UE_LOG(LogTemp, Error, TEXT("❌ 에디터 ListenSocket 생성 실패"));
        return;
    }

    GetWorld()->GetTimerManager().SetTimer(ListenTimerHandle, this, &AMySocketServerEditor::AcceptClients, 0.2f, true);
    UE_LOG(LogTemp, Log, TEXT("📡 AMySocketServerEditor 리스닝 시작 (Port: %d)"), Port);
}

void AMySocketServerEditor::AcceptClients()
{
    bool bHasPending;
    if (ListenSocket->HasPendingConnection(bHasPending) && bHasPending)
    {
        TSharedRef<FInternetAddr> RemoteAddress = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
        ClientSocket = ListenSocket->Accept(*RemoteAddress, TEXT("EditorClient"));

        if (ClientSocket)
        {
            UE_LOG(LogTemp, Warning, TEXT("✅ 에디터 클라이언트 접속됨: %s"), *RemoteAddress->ToString(true));
        }
    }
}

void AMySocketServerEditor::HandleIncomingCommand(const FString& Command)
{
    // ✅ py "..." 명령 처리
    if (Command.StartsWith("py "))
    {
        FString ScriptAndArgs = Command.RightChop(3).TrimStartAndEnd();  // remove "py "
        FString FinalCommand = FString::Printf(TEXT("py %s"), *ScriptAndArgs);

        if (GEditor)
        {
            GEditor->Exec(GetWorld(), *FinalCommand);
            UE_LOG(LogTemp, Log, TEXT("🟢 Python 실행 명령 전달됨: %s"), *FinalCommand);
        }
        else
        {
            UE_LOG(LogTemp, Error, TEXT("❌ GEditor 사용 불가 - Python 실행 실패"));
        }

        return;
    }

    // 기존 IMPORT_FBX 처리
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

    // ⛔ 알 수 없는 명령
    UE_LOG(LogTemp, Warning, TEXT("⚠️ 알 수 없는 명령 (에디터 전용): %s"), *Command);
}


void AMySocketServerEditor::ExecutePythonAfterDelay(const FString& ScriptPath)
{
    FTimerHandle TimerHandle;
    GetWorld()->GetTimerManager().SetTimer(TimerHandle, [ScriptPath]()
        {
            if (GEditor)
            {
                GEditor->Exec(nullptr, *FString::Printf(TEXT("py \"%s\""), *ScriptPath));
                UE_LOG(LogTemp, Log, TEXT("🟢 Python 스크립트 실행됨: %s"), *ScriptPath);
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

#endif
