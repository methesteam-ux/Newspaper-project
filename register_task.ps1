# [나만의 신문] Windows 작업 스케줄러 스마트 자동 등록
#   - 매일 지정 시각(기본 08:00)에 run_daily.bat 실행
#   - WakeToRun        : PC가 절전(Sleep) 상태여도 깨어나서 발행
#   - StartWhenAvailable: 지정 시각에 PC가 꺼져 있었다면 켜진 직후 즉시 발행
param(
    [string]$Time = "08:00",
    [string]$TaskName = "MyDailyNewspaper_MorningPublish",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Bat = Join-Path $Root "run_daily.bat"
$Line = "=" * 66

Write-Host $Line
Write-Host "   [나만의 신문] Windows 작업 스케줄러 스마트 자동 등록"
Write-Host $Line

if ($Unregister) {
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "[OK] 작업 '$TaskName' 을(를) 삭제했습니다."
    } catch {
        Write-Host "[!] 삭제 실패: $($_.Exception.Message)"
        exit 1
    }
    exit 0
}

if (-not (Test-Path $Bat)) {
    Write-Host "[!] run_daily.bat 을 찾을 수 없습니다: $Bat"
    exit 1
}

Write-Host "[*] 등록할 작업 이름 : $TaskName"
Write-Host "[*] 실행할 배치 파일 : $Bat"
Write-Host "[*] 실행 예정 주기   : 매일 $Time"

try {
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Bat`"" -WorkingDirectory $Root
    $Trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $Settings = New-ScheduledTaskSettingsSet `
        -WakeToRun `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
        -Description "나만의 신문: 매일 $Time 에 Gmail News 라벨 기사로 신문을 발행합니다." -Force | Out-Null
} catch {
    Write-Host ""
    Write-Host "[!] 등록 실패: $($_.Exception.Message)"
    Write-Host "    register_task.bat 을 마우스 우클릭 -> [관리자 권한으로 실행] 해 보세요."
    exit 1
}

Write-Host ""
Write-Host "[등록 성공] 작업 스케줄러에 등록되었습니다!"
Write-Host ""
Write-Host "   [적용된 스마트 무인 옵션]"
Write-Host "   1. 매일 $Time 에 자동으로 신문을 수집/발행합니다."
Write-Host "   2. PC가 절전(Sleep) 상태여도 스스로 깨어나서 발행합니다. (WakeToRun)"
Write-Host "   3. $Time 에 PC가 꺼져 있었다면 켜진 직후 즉시 발행합니다. (StartWhenAvailable)"
Write-Host ""
Write-Host "[*] 상태 확인 명령어 : schtasks /query /tn `"$TaskName`" /fo list"
Write-Host "[*] 작업 삭제 명령어 : register_task.bat -Unregister"
Write-Host $Line
