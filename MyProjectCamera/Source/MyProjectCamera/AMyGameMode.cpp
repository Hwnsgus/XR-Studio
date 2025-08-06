#include "AMyGameMode.h"
#include "AMyPlayerController.h" // 필요한 경우

AMyGameMode::AMyGameMode()
{
    PlayerControllerClass = AMyPlayerController::StaticClass();
    DefaultPawnClass = nullptr; // 필요한 경우 지정
}
