#include "AMyGameMode.h"
#include "AMyPlayerController.h" // �ʿ��� ���

AMyGameMode::AMyGameMode()
{
    PlayerControllerClass = AMyPlayerController::StaticClass();
    DefaultPawnClass = nullptr; // �ʿ��� ��� ����
}
