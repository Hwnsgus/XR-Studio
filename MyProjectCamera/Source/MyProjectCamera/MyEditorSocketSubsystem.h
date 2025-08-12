#pragma once

#include "CoreMinimal.h"
#include "EditorSubsystem.h"
#include "Sockets.h"
#include "SocketSubsystem.h"

#include "MyEditorSocketSubsystem.generated.h"

UCLASS()
class MYPROJECTCAMERA_API UMyEditorSocketSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

private:
    void StartListening(int32 Port);
    void StopListening();
    void AcceptClients();
    void PumpClient();
    void HandleIncomingCommand(const FString& Command);
    void ExecPython(const FString& PyCommand);
    bool IsPIEActive() const;

private:
    FSocket* ListenSocket = nullptr;
    FSocket* ClientSocket = nullptr;

    FTSTicker::FDelegateHandle TickerHandle;   // 0.1s¸¶´Ù Accept/Pump
};
