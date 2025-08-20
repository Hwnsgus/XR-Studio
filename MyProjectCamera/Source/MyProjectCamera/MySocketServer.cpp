#include "MySocketServer.h"
#include "EngineUtils.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Common/TcpSocketBuilder.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Editor.h" // GEditor
#include "Engine/StaticMeshActor.h"

AMySocketServer::AMySocketServer()
{
    PrimaryActorTick.bCanEverTick = true;
}

void AMySocketServer::BeginPlay()
{
    Super::BeginPlay();
    StartListening(9999);
}

FString AMySocketServer::GetStaticMeshActorNames()
{
    FString Result;
    for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
    {
        Result += It->GetName() + LINE_TERMINATOR;
    }
    return Result;
}


void AMySocketServer::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    if (!ClientSocket)
    {
        static int SkipLog = 0;
        if (++SkipLog % 30 == 0)
            UE_LOG(LogTemp, Warning, TEXT("❌ ClientSocket is NULL"));
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

        Data.Add(0);

        const char* CharData = reinterpret_cast<const char*>(Data.GetData());
        if (!CharData || CharData[0] == '\0')
        {
            UE_LOG(LogTemp, Error, TEXT("❌ CharData is empty or null"));
            return;
        }

        FString Command = FString(ANSI_TO_TCHAR(CharData));
        Command.TrimStartAndEndInline();
        Command.ReplaceInline(TEXT("\n"), TEXT(""));
        Command.ReplaceInline(TEXT("\r"), TEXT(""));
        Command.ReplaceInline(TEXT("\0"), TEXT(""));

        // 👇 이 부분 꼭 있어야 함!
        Command = Command.Replace(TEXT("\x01"), TEXT("")).Replace(TEXT("\x02"), TEXT("")).Replace(TEXT("\x03"), TEXT("")).Replace(TEXT("\xFF"), TEXT("")).Replace(TEXT("\xFE"), TEXT(""));

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

        // ✅ 추가: LIST_STATIC (StaticMeshActor만)
        if (Tokens.Num() >= 1 && Tokens[0].Equals(TEXT("LIST_STATIC"), ESearchCase::IgnoreCase))
        {
            FString ActorNames = GetStaticMeshActorNames();
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

// 프리셋 로드 
FString AMySocketServer::CmdLoadPreset(const FString& Name, float Ox, float Oy, float Oz)
{
    const FString Path = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("ScenePresets"), Name + TEXT(".json"));
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *Path))
        return FString::Printf(TEXT("❌ 프리셋 없음: %s"), *Path);

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
        return TEXT("❌ JSON 파싱 실패");

    const TArray<TSharedPtr<FJsonValue>>* Actors;
    if (!Root->TryGetArrayField(TEXT("actors"), Actors))
        return TEXT("⚠️ actors 없음");

    int32 Count = 0;
    for (const TSharedPtr<FJsonValue>& V : *Actors)
    {
        const TSharedPtr<FJsonObject> A = V->AsObject();
        if (!A.IsValid()) continue;
        FString ClassPath;  A->TryGetStringField(TEXT("class"), ClassPath);
        if (!ClassPath.EndsWith(TEXT("StaticMeshActor"))) continue;

        FString MeshPath;   A->TryGetStringField(TEXT("static_mesh"), MeshPath);
        UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *MeshPath);
        if (!Mesh) continue;

        auto Arr3 = [](const TArray<TSharedPtr<FJsonValue>>& Arr) { return FVector(Arr[0]->AsNumber(), Arr[1]->AsNumber(), Arr[2]->AsNumber()); };

        const TArray<TSharedPtr<FJsonValue>>& LocA = A->GetArrayField(TEXT("location"));
        const TArray<TSharedPtr<FJsonValue>>& RotA = A->GetArrayField(TEXT("rotation"));
        const TArray<TSharedPtr<FJsonValue>>& ScaA = A->GetArrayField(TEXT("scale"));

        FVector Loc = Arr3(LocA) + FVector(Ox, Oy, Oz);
        FRotator Rot(RotA[0]->AsNumber(), RotA[1]->AsNumber(), RotA[2]->AsNumber());
        FVector S = Arr3(ScaA);

        AStaticMeshActor* SMA = GetWorld()->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), Loc, Rot);
        if (!SMA) continue;

        UStaticMeshComponent* SMC = SMA->GetStaticMeshComponent();
        if (SMC)
        {
            SMC->SetMobility(EComponentMobility::Movable); // 초기부터 Movable
            SMC->SetStaticMesh(Mesh);
            SMC->SetWorldScale3D(S);

            const TArray<TSharedPtr<FJsonValue>>* Mats;
            if (A->TryGetArrayField(TEXT("materials"), Mats))
            {
                int32 Idx = 0;
                for (const TSharedPtr<FJsonValue>& MV : *Mats)
                {
                    const FString MPath = MV->AsString();
                    if (!MPath.IsEmpty())
                    {
                        if (UMaterialInterface* MI = LoadObject<UMaterialInterface>(nullptr, *MPath))
                            SMC->SetMaterial(Idx, MI);
                    }
                    ++Idx;
                }
            }
        }

        FString Label;
        if (A->TryGetStringField(TEXT("label"), Label)) { SMA->SetActorLabel(Label); }
        ++Count;
    }
    return FString::Printf(TEXT("OK Loaded %d"), Count);
}

// 현재 씬의 모든 StaticMeshActor를 JSON으로 저장
FString AMySocketServer::CmdSavePreset(const FString& Name)
{
    TArray<TSharedPtr<FJsonValue>> OutActors;
    for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
    {
        AStaticMeshActor* A = *It;
        UStaticMeshComponent* C = A->GetStaticMeshComponent();
        if (!C || !C->GetStaticMesh()) continue;

        TSharedPtr<FJsonObject> O = MakeShared<FJsonObject>();
        O->SetStringField(TEXT("label"), A->GetActorLabel());
        O->SetStringField(TEXT("class"), TEXT("/Script/Engine.StaticMeshActor"));
        const FVector L = A->GetActorLocation();
        const FRotator R = A->GetActorRotation();
        const FVector S = A->GetActorScale3D();
        auto Vec = [](const FVector& V) { TArray<TSharedPtr<FJsonValue>> A; A.Add(MakeShared<FJsonValueNumber>(V.X)); A.Add(MakeShared<FJsonValueNumber>(V.Y)); A.Add(MakeShared<FJsonValueNumber>(V.Z)); return A; };
        auto Rot = [](const FRotator& R) { TArray<TSharedPtr<FJsonValue>> A; A.Add(MakeShared<FJsonValueNumber>(R.Pitch)); A.Add(MakeShared<FJsonValueNumber>(R.Yaw)); A.Add(MakeShared<FJsonValueNumber>(R.Roll)); return A; };
        O->SetArrayField(TEXT("location"), Vec(L));
        O->SetArrayField(TEXT("rotation"), Rot(R));
        O->SetArrayField(TEXT("scale"), Vec(S));
        O->SetStringField(TEXT("static_mesh"), C->GetStaticMesh()->GetPathName());
        // materials
        TArray<TSharedPtr<FJsonValue>> Mats;
        const int32 MCount = C->GetNumMaterials();
        for (int32 i = 0; i < MCount; ++i)
        {
            if (UMaterialInterface* MI = C->GetMaterial(i))
                Mats.Add(MakeShared<FJsonValueString>(MI->GetPathName()));
            else
                Mats.Add(MakeShared<FJsonValueString>(TEXT("")));
        }
        O->SetArrayField(TEXT("materials"), Mats);
        O->SetStringField(TEXT("mobility"), TEXT("MOVABLE")); // 런타임 저장에선 간단화

        OutActors.Add(MakeShared<FJsonValueObject>(O));
    }

    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("version"), 1);
    Root->SetStringField(TEXT("name"), Name);
    Root->SetArrayField(TEXT("actors"), OutActors);

    FString JsonOut;
    const TSharedRef<TJsonWriter<>> W = TJsonWriterFactory<>::Create(&JsonOut);
    FJsonSerializer::Serialize(Root.ToSharedRef(), W);

    const FString Path = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("ScenePresets"), Name + TEXT(".json"));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
    if (!FFileHelper::SaveStringToFile(JsonOut, *Path))
        return TEXT("❌ 저장 실패");
    return FString::Printf(TEXT("OK Saved: %s"), *Path);
}


FString AMySocketServer::HandleCommand(const FString& Command)
{
    TArray<FString> Tokens;
    Command.ParseIntoArrayWS(Tokens);

    UE_LOG(LogTemp, Warning, TEXT("🧪 Tokens (%d):"), Tokens.Num());
    for (int i = 0; i < Tokens.Num(); ++i)
    {
        UE_LOG(LogTemp, Warning, TEXT("    [%d] %s"), i, *Tokens[i]);
    }


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
                USceneComponent* RootComp = It->GetRootComponent();
                if (!RootComp)
                    return FString::Printf(TEXT("❌ '%s' 액터의 루트 컴포넌트를 찾을 수 없습니다."), *ActorName);

                if (RootComp->Mobility != EComponentMobility::Movable)
                    return FString::Printf(TEXT("❌ '%s'의 Mobility가 'Movable'이 아닙니다."), *ActorName);

                It->SetActorLocation(FVector(X, Y, Z));
                return FString::Printf(TEXT("✅ %s 이동 완료: (%.1f, %.1f, %.1f)"), *ActorName, X, Y, Z);
            }
        }
        return FString::Printf(TEXT("❌ '%s' 이름의 액터를 찾을 수 없음"), *ActorName);
    }

    else if (Tokens[0] == "GET_LOCATION" && Tokens.Num() >= 2)
    {
        FString ActorName = Tokens[1];

        for (TActorIterator<AActor> It(GetWorld()); It; ++It)
        {
            if (It->GetName().Equals(ActorName, ESearchCase::IgnoreCase))
            {
                FVector Loc = It->GetActorLocation();
                return FString::Printf(TEXT("Location: %.1f %.1f %.1f"), Loc.X, Loc.Y, Loc.Z);
            }
        }
        return FString::Printf(TEXT("❌ 액터 '%s'을(를) 찾을 수 없습니다."), *ActorName);
    }


    else if (Tokens[0] == "SET_TEXTURE" && Tokens.Num() >= 5)
    {
        FString ActorName = Tokens[1];
        int32 SlotIndex = FCString::Atoi(*Tokens[2]);
        FString ParamName = Tokens[3];
        FString TexturePath = Tokens[4];

        UTexture* NewTexture = Cast<UTexture>(StaticLoadObject(UTexture::StaticClass(), nullptr, *TexturePath));
        if (!NewTexture) return TEXT("❌ 텍스처 로드 실패");

        for (TActorIterator<AActor> It(GetWorld()); It; ++It)
        {
            if (It->GetName().Equals(ActorName, ESearchCase::IgnoreCase))
            {
                TArray<UStaticMeshComponent*> MeshComponents;
                It->GetComponents<UStaticMeshComponent>(MeshComponents);

                for (UStaticMeshComponent* MeshComp : MeshComponents)
                {
                    if (MeshComp->GetNumMaterials() <= SlotIndex)
                        continue;

                    UMaterialInstanceDynamic* DynMat = MeshComp->CreateAndSetMaterialInstanceDynamic(SlotIndex);
                    if (!DynMat) continue;

                    DynMat->SetTextureParameterValue(*ParamName, NewTexture);
                    return FString::Printf(TEXT("✅ '%s'의 %d번 슬롯 [%s] 텍스처 교체 성공"), *ActorName, SlotIndex, *ParamName);
                }
            }
        }

        return TEXT("❌ 적용 실패 (액터 또는 슬롯 없음)");
    }

    else if (Tokens[0] == "GET_TEXTURES" && Tokens.Num() >= 2)
    {
        FString ActorName = Tokens[1];

        for (TActorIterator<AActor> It(GetWorld()); It; ++It)
        {
            if (It->GetName().Equals(ActorName, ESearchCase::IgnoreCase))
            {
                FString Result;
                TArray<UStaticMeshComponent*> MeshComponents;
                It->GetComponents<UStaticMeshComponent>(MeshComponents);

                for (UStaticMeshComponent* MeshComp : MeshComponents)
                {
                    int32 MatCount = MeshComp->GetNumMaterials();
                    for (int32 i = 0; i < MatCount; ++i)
                    {
                        UMaterialInterface* Mat = MeshComp->GetMaterial(i);
                        if (!Mat) continue;

                        Result += FString::Printf(TEXT("Material Slot %d: %s\n"), i, *Mat->GetName());

                        TArray<UTexture*> Textures;
                        Mat->GetUsedTextures(Textures, EMaterialQualityLevel::High, false, ERHIFeatureLevel::SM5, true);

                        for (UTexture* Tex : Textures)
                        {
                            if (Tex)
                                Result += FString::Printf(TEXT("    └ Texture: %s\n"), *Tex->GetName());
                        }
                    }
                }

                return Result.IsEmpty() ? TEXT("⚠️ 머티리얼 또는 텍스처가 없음") : Result;
            }
        }

        return FString::Printf(TEXT("❌ '%s' 이름의 액터를 찾을 수 없음"), *ActorName);
    }

    else if (Tokens[0] == "SET_MATERIAL" && Tokens.Num() >= 4)
    {
        FString ActorName = Tokens[1];
        int32 SlotIndex = FCString::Atoi(*Tokens[2]);

        // 3번 인덱스부터 끝까지 다시 합쳐 경로 복원
        FString MaterialPath;
        {
            TArray<FString> TailTokens;
            for (int32 i = 3; i < Tokens.Num(); ++i) { TailTokens.Add(Tokens[i]); }
            MaterialPath = FString::Join(TailTokens, TEXT(" "));

            // 에디터 서브시스템의 CleanArg와 유사한 정리: 개행/따옴표 제거
            MaterialPath.ReplaceInline(TEXT("\r"), TEXT(""));
            MaterialPath.ReplaceInline(TEXT("\n"), TEXT(""));
            MaterialPath.TrimStartAndEndInline();
            if ((MaterialPath.StartsWith(TEXT("\"")) && MaterialPath.EndsWith(TEXT("\""))) ||
                (MaterialPath.StartsWith(TEXT("'")) && MaterialPath.EndsWith(TEXT("'"))))
            {
                MaterialPath = MaterialPath.Mid(1, MaterialPath.Len() - 2);
                MaterialPath.TrimStartAndEndInline();
            }
        }

        UMaterialInterface* NewMaterial =
            Cast<UMaterialInterface>(StaticLoadObject(UMaterialInterface::StaticClass(), nullptr, *MaterialPath));
        if (!NewMaterial) return TEXT("❌ 머티리얼 로드 실패");

        for (TActorIterator<AActor> It(GetWorld()); It; ++It)
        {
            if (It->GetName().Equals(ActorName, ESearchCase::IgnoreCase))
            {
                TArray<UStaticMeshComponent*> MeshComponents;
                It->GetComponents<UStaticMeshComponent>(MeshComponents);

                for (UStaticMeshComponent* MeshComp : MeshComponents)
                {
                    if (MeshComp->GetNumMaterials() <= SlotIndex) continue;
                    MeshComp->SetMaterial(SlotIndex, NewMaterial);
                    return FString::Printf(TEXT("✅ '%s'의 %d번 슬롯 머티리얼 교체 성공"), *ActorName, SlotIndex);
                }
            }
        }
        return TEXT("❌ 적용 실패 (액터 또는 슬롯 없음)");
        }


    else if (Tokens[0] == "GET_MATERIALS")
    {
        FString Path = Tokens.Num() >= 2 ? Tokens[1] : "/Game";
        TArray<FAssetData> Assets;
        FARFilter Filter;
        Filter.ClassPaths.Add(UMaterialInterface::StaticClass()->GetClassPathName());
        Filter.PackagePaths.Add(*Path);
        Filter.bRecursivePaths = true;

        FAssetRegistryModule& AssetRegistry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
        AssetRegistry.Get().GetAssets(Filter, Assets);

        FString Result;
        for (const FAssetData& Asset : Assets)
        {
            Result += Asset.GetObjectPathString() + LINE_TERMINATOR;
        }

        return Result.IsEmpty() ? TEXT("⚠️ 머티리얼 없음") : Result;
    }

    else if (Tokens[0] == "GET_BLUEPRINTS")
    {
        FString Path = Tokens.Num() >= 2 ? Tokens[1] : "/Game";
        TArray<FAssetData> Assets;
        FARFilter Filter;
        Filter.ClassPaths.Add(FTopLevelAssetPath(TEXT("/Script/Engine"), TEXT("Blueprint")));
        Filter.PackagePaths.Add(*Path);
        Filter.bRecursivePaths = true;

        FAssetRegistryModule& AssetRegistry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
        AssetRegistry.Get().GetAssets(Filter, Assets);

        FString Result;
        for (const FAssetData& Asset : Assets)
        {
            Result += Asset.GetObjectPathString() + TEXT("_C") + LINE_TERMINATOR;
        }

        return Result.IsEmpty() ? TEXT("⚠️ 블루프린트 없음") : Result;
    }

    else if (Tokens.Num() >= 2 && Tokens[0] == "IMPORT_FBX")
    {
#if WITH_EDITOR
        return TEXT("❌ 에디터 모드에서만 사용 가능합니다. (PIE 상태에서는 FBX 임포트 불가)");
#else
        return TEXT("❌ 에디터 모드에서만 사용 가능합니다.");
#endif
    }

    else if (Tokens[0] == "LOAD_PRESET" && Tokens.Num() >= 2)
    {
        const FString Name = Tokens[1];
        float Ox = 0, Oy = 0, Oz = 0;
        if (Tokens.Num() >= 5) { Ox = FCString::Atof(*Tokens[2]); Oy = FCString::Atof(*Tokens[3]); Oz = FCString::Atof(*Tokens[4]); }
        return CmdLoadPreset(Name, Ox, Oy, Oz);
        }

        // (원하면) 저장도:
    else if (Tokens[0] == "SAVE_PRESET" && Tokens.Num() >= 2)
    {
        const FString Name = Tokens[1];
        return CmdSavePreset(Name);
        }


    return TEXT("❌ 알 수 없는 명령");
}

FString AMySocketServer::GetAllActorNames()
{
    FString Result;
    for (TActorIterator<AActor> It(GetWorld()); It; ++It)
    {
        FString Name = It->GetName();
        Result += Name + LINE_TERMINATOR;
    }
    return Result;
}

void AMySocketServer::ExecutePythonAfterDelay(const FString& ScriptPath)
{
    FTimerHandle TimerHandle;
    GetWorld()->GetTimerManager().SetTimer(TimerHandle, [this, ScriptPath]()
        {
            if (GEditor)
            {
                GEditor->Exec(GetWorld(), *FString::Printf(TEXT("py \"%s\""), *ScriptPath));
                UE_LOG(LogTemp, Log, TEXT("⏱️ 지연된 Python 스크립트 실행: %s"), *ScriptPath);
            }
            else
            {
                UE_LOG(LogTemp, Error, TEXT("❌ GEditor 사용 불가 - Python 실행 실패"));
            }
        }, 0.1f, false);
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





// MySocketServer.cpp


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