# Generates a synthetic 2-speaker English interview (Windows text-to-speech) for smoke-testing the
# pipeline. It is NOT a substitute for real recordings (no Twi, no accents, no noise).
Add-Type -AssemblyName System.Speech
$out = Join-Path $PSScriptRoot "audio\sample_english_tts.wav"
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = $synth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo.Name }
$interviewer = $voices[0]
$stakeholder = if ($voices.Count -gt 1) { $voices[1] } else { $voices[0] }

$script = @(
  @($interviewer, "Good morning. Thanks for making time. Can you tell me how you currently track customer orders?"),
  @($stakeholder, "Right now we write every order in a big notebook, and at the end of the day someone types it into Excel. It takes about two hours every evening."),
  @($interviewer, "What would you like the new system to do?"),
  @($stakeholder, "The sales staff should be able to record an order on their phone while they are with the customer. The system must send the customer an SMS confirmation with the order number."),
  @($interviewer, "Are there any rules about payments?"),
  @($stakeholder, "Yes. Orders above five thousand cedis need approval from the branch manager before they are processed. And customers can pay with mobile money or cash."),
  @($interviewer, "How fast does it need to be?"),
  @($stakeholder, "It should be fast. Our network in the branches is not reliable, so it must keep working offline and sync when the connection comes back."),
  @($interviewer, "Who else will use it?"),
  @($stakeholder, "The accountant needs a monthly sales report per branch, exported to Excel. Only managers should see the profit figures. I am not sure yet whether we need it in Twi as well, we have to ask the branch staff.")
)

$pb = New-Object System.Speech.Synthesis.PromptBuilder
foreach ($line in $script) {
  $pb.StartVoice($line[0]); $pb.AppendText($line[1]); $pb.EndVoice()
  $pb.AppendBreak([TimeSpan]::FromMilliseconds(700))
}
$synth.SetOutputToWaveFile($out)
$synth.Speak($pb)
$synth.Dispose()
"Wrote $out using voices: $interviewer / $stakeholder"
