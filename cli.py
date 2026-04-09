#!/usr/bin/env python3
import os
import sys
import inquirer
from rich.console import Console
from rich.status import Status
from rich.panel import Panel
from rich.text import Text

# Add the project directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.downloader import DownloadService
from app.services.ffmpeg import FFmpegService
from app.services.whisper import WhisperService
from app.services.youtube_upload import YouTubeUploadService
from app.services.workflow import WorkflowService
from app.services.veo_service import VeoService, prompts_from_script
from app.ai_shorts.workflow_service import WorkflowService as AIShortsWorkflow
from app.config import settings

console = Console()

_downloader = DownloadService()
_ffmpeg = FFmpegService()
_whisper = WhisperService()
_workflow = WorkflowService()
_veo = VeoService()


def print_header():
    console.clear()
    header = Panel(
        Text("🎬 YouTube Shorts Automation CLI 🎬\n\nFully Local • OpenRouter AI • YouTube Auto-Upload", justify="center", style="bold cyan"),
        border_style="cyan"
    )
    console.print(header)


def prompt_video_url() -> str:
    questions = [
        inquirer.Text('url', message="Enter the YouTube URL")
    ]
    return inquirer.prompt(questions)['url']


def step_download():
    url = prompt_video_url()
    with Status("[bold yellow]Downloading high-quality video using yt-dlp...", spinner="dots") as status:
        try:
            dl = _downloader.download(url, quality="best")
            console.print(f"[bold green]✔ Download Complete![/] Saved to: {dl['filePath']}")
        except Exception as e:
            console.print(f"[bold red]❌ Download Failed:[/] {e}")


def step_crop():
    questions = [
        inquirer.Text('path', message="Enter the absolute path to the .mp4 file"),
        inquirer.Text('start', message="Start time in seconds", default="0"),
        inquirer.Text('duration', message="Duration in seconds", default="60"),
    ]
    ans = inquirer.prompt(questions)
    
    with Status("[bold yellow]Rendering 9:16 Blurred Background Short via FFmpeg...", spinner="arc") as status:
        try:
            cropped = _ffmpeg.crop_to_vertical(
                input_path=ans['path'],
                duration_sec=int(ans['duration']),
                start_sec=int(ans['start'])
            )
            console.print(f"[bold green]✔ Crop Complete![/] Saved to: {cropped}")
        except Exception as e:
            console.print(f"[bold red]❌ Crop Failed:[/] {e}")


def step_transcribe():
    questions = [
        inquirer.Text('path', message="Enter the absolute path to the cropped _short.mp4 file")
    ]
    ans = inquirer.prompt(questions)
    
    with Status("[bold yellow]Processing Audio through OpenAI Whisper (This takes a few minutes)...", spinner="bouncingBar") as status:
        try:
            srt_path = _whisper.transcribe(video_path=ans['path'], model="base")
            console.print(f"[bold green]✔ Transcription Complete![/] Subtitles saved at: {srt_path}")
        except Exception as e:
            console.print(f"[bold red]❌ Whisper Failed:[/] {e}")


def step_burn_captions():
    questions = [
        inquirer.Text('video', message="Enter the absolute path to the _short.mp4 file"),
        inquirer.Text('srt', message="Enter the absolute path to the .srt file"),
        inquirer.Text('heading', message="Enter a catchy Heading Text (Optional)", default=settings.default_heading_text),
    ]
    ans = inquirer.prompt(questions)
    
    with Status("[bold yellow]Burning Captions and Graphics into video natively...", spinner="dots2") as status:
        try:
            final_path, _ = _ffmpeg.burn_captions(
                video_path=ans['video'],
                srt_path=ans['srt'],
                heading_text=ans['heading'] if ans['heading'] else None
            )
            console.print(f"[bold green]✔ Captioning Complete![/] Final short exported to: {final_path}")
        except Exception as e:
            console.print(f"[bold red]❌ Caption Burn Failed:[/] {e}")


def step_ai_metadata():
    questions = [
        inquirer.Text('title', message="Original Video Title"),
        inquirer.Text('channel', message="Channel Name", default="Unknown"),
    ]
    ans = inquirer.prompt(questions)
    
    with Status("[bold yellow]Connecting to OpenRouter Mistral AI...", spinner="aesthetic") as status:
        try:
            meta = _workflow.generate_metadata(ans['title'], ans['channel'], "0", "")
            console.print("[bold green]✔ AI Generation Complete![/]")
            console.print(Panel(f"[bold cyan]Headings:[/] {meta.get('title')}\n[bold cyan]Desc:[/] {meta.get('description')}\n[bold cyan]Tags:[/] {meta.get('hashtags')}", title="Viral Metadata"))
        except Exception as e:
            console.print(f"[bold red]❌ AI Generation Failed:[/] {e}")


def step_autonomous(limit=5):
    console.print("\n[bold magenta]🚀 INITIATING MASS AUTONOMOUS DEPLOYMENT 🚀[/]")
    
    # 0. Auth
    with Status("[cyan]Step 0/8: Validating YouTube Authentication...", spinner="dots") as status:
        try:
            yt_svc = YouTubeUploadService()
        except Exception as e:
            console.print(f"[bold red]❌ YouTube Auth Failed. Please run python auth.py first.[/]")
            return

    with Status("[cyan]Step 1/8: Analyzing Global Trends to find today's #1 top category...", spinner="dots") as status:
        trending_categories = _workflow.get_trending_categories(limit=1)
        if not trending_categories:
            console.print("[bold red]❌ Failed to find a trending category.[/]")
            return
            
        top_cat = trending_categories[0]
        cat_id = top_cat["id"]
        cat_name = top_cat["name"]

    console.print(f"[bold green]🔥 Today's #1 Global Category is: {cat_name} 🔥[/]")
    console.print(f"[bold green]Starting Daily Sweep for {limit} Videos focusing purely on '{cat_name}'[/]\n")

    # 1. Fetch N videos
    with Status(f"[cyan]Step 2/8: Deep searching {limit} trending videos in '{cat_name}'...", spinner="dots") as status:
        videos = _workflow.fetch_trending_videos(category_id=cat_id, limit=limit)
        if not videos:
            console.print(f"[bold yellow]⚠️ No fresh viral videos found in category {cat_name}. Exiting...[/]")
            return

    for idx, best in enumerate(videos, 1):
        console.print(Panel(f"[bold cyan]Deploying Target {idx} / {len(videos)} | Views: {best['viewCount']}[/]\n{best['title']}", border_style="cyan"))
        
        video_id = best['videoId']
        try:
            # 2. Download
            with Status("[cyan]Step 3/8: Downloading pristine source video...", spinner="dots") as status:
                dl = _downloader.download(best['videoUrl'], quality="best")

            # 3. Crop
            with Status("[cyan]Step 4/8: Applying 9:16 Blurred Background & Anti-Copyright Engine...", spinner="dots") as status:
                cropped_path = _ffmpeg.crop_to_vertical(input_path=dl['filePath'])

            # 4. Transcribe
            with Status("[magenta]Step 5/8: Thinking... (Whisper AI processing Audio)[/]", spinner="bouncingBar") as status:
                srt_path = _whisper.transcribe(video_path=cropped_path, model="base")

            # 5. Metadata
            with Status("[magenta]Step 6/8: Generating Viral Short Copy (Mistral-small)...", spinner="aesthetic") as status:
                meta = _workflow.generate_metadata(
                    best['title'],
                    best['channelTitle'],
                    best['viewCount'],
                    best['tags'],
                    cat_name,
                    original_video_id=video_id,
                )
                heading = meta.get('title', "WAIT FOR IT...")

            # 6. Burn
            with Status("[cyan]Step 7/8: Burning animated 3D Subtitles and Heading...", spinner="dots") as status:
                final_path, _ = _ffmpeg.burn_captions(video_path=cropped_path, srt_path=srt_path, heading_text=heading)

            # 7. Upload
            with Status("[bold green]Step 8/8: Uploading to Youtube and Ping Telegram!!!", spinner="earth") as status:
                try:
                    vid = yt_svc.upload_short(
                        video_path=final_path,
                        title=heading,
                        description=meta.get("full_description", heading),
                        category_id=cat_id,
                        tags=[tag.replace('#', '') for tag in meta.get("hashtags", "").split()]
                    )
                    yt_url = f"https://youtube.com/shorts/{vid}"
                except Exception as e:
                    console.print(f"[bold red]❌ Initial YouTube Upload Failed:[/] {e}")
                    yt_url = final_path

                try:
                    _workflow.send_telegram_alert(heading, yt_url, best['title'], best['viewCount'])
                    _workflow.send_telegram_video(final_path, caption=f"🎥 *{heading}*\n\n_{meta.get('description', '')}_")
                except Exception as e:
                    console.print(f"[bold red]❌ Telegram push Failed:[/] {e}")

            # Only mark processed after a successful pipeline run (avoid “false processed”)
            _workflow.mark_video_processed(video_id)
            console.print(f"[bold green]✔ Deploy {idx} Successful![/] {yt_url}\n")
        except Exception as e:
            console.print(f"[bold red]❌ Deploy {idx} Failed:[/] {e}\n")
    
    console.print(Panel("[bold green]🎉 FULL DAILY SWEEP COMPLETE! All distinct videos deployed! 🎉[/]", border_style="green"))




def step_veo3_from_prompt():
    """Standalone Veo 3 video generation from a raw user prompt (with audio)."""
    console.print(
        Panel(
            "[bold cyan]🎬 Veo 3 – Generate Video from Prompt[/]\n"
            "[dim]Uses Google Veo 3 (veo-3-0-generate-preview) with native audio generation.[/]",
            border_style="cyan",
        )
    )

    console.print("\n[bold yellow]Describe the video you want to generate:[/]")
    console.print("[dim](Paste your prompt and press Enter. Please remove any blank lines if pasting multiple paragraphs.)[/]")
    
    prompt_text = ""
    while not prompt_text:
        try:
            prompt_text = input("\nPrompt> ").strip()
        except EOFError:
            return
        except KeyboardInterrupt:
            return
            
    if not prompt_text:
        return

    questions = [
        inquirer.List(
            "aspect_ratio",
            message="Aspect ratio",
            choices=["9:16 (Portrait / Shorts)", "16:9 (Landscape / YouTube)", "1:1 (Square)"],
            default="9:16 (Portrait / Shorts)",
        ),
        inquirer.List(
            "audio",
            message="Generate audio with the video?",
            choices=["Yes – generate ambient audio (Veo 3 native)", "No – silent video only"],
            default="Yes – generate ambient audio (Veo 3 native)",
        ),
    ]
    ans = inquirer.prompt(questions)
    if not ans:
        return
    aspect_map = {
        "9:16 (Portrait / Shorts)": "9:16",
        "16:9 (Landscape / YouTube)": "16:9",
        "1:1 (Square)": "1:1",
    }
    aspect_ratio = aspect_map.get(ans["aspect_ratio"], "9:16")
    generate_audio = ans["audio"].startswith("Yes")

    audio_label = "🔊 with audio" if generate_audio else "🔇 silent"
    console.print(
        f"\n[bold green]Prompt:[/] {prompt_text}\n"
        f"[bold green]Aspect:[/] {aspect_ratio}  [bold green]Audio:[/] {audio_label}\n"
    )

    with Status(
        f"[bold yellow]⏳ Sending to Veo 3... This can take 2–7 minutes. Please wait...",
        spinner="earth",
    ) as status:
        try:
            saved_path = _veo.generate_video_from_prompt(
                prompt=prompt_text,
                aspect_ratio=aspect_ratio,
                generate_audio=generate_audio,
            )
        except Exception as e:
            console.print(f"[bold red]❌ Veo 3 generation failed:[/] {e}")
            return

    if saved_path:
        console.print(
            Panel(
                f"[bold green]✔ Video Generated Successfully![/]\n\n"
                f"[bold cyan]Saved to:[/] {saved_path}\n"
                f"[dim]Aspect ratio: {aspect_ratio} | Audio: {audio_label}[/]",
                title="🎬 Veo 3 Result",
                border_style="green",
            )
        )
    else:
        console.print(
            "[bold red]❌ Video generation failed.[/] "
            "Check that GOOGLE_GENAI_API_KEY is set and your quota allows Veo 3 access."
        )



def step_generate_ai_short():
    console.print(Panel("[bold cyan]🤖 AI Generative Shorts Pipeline[/]\n[dim]Fully autonomous local generation (Story -> Images -> Audio -> FFmpeg)[/]", border_style="cyan"))
    
    cat_choices = ["🔄  Auto (rotation)", "🧸  kids_fun_story", "👻  horror_short", "🔥  motivational_story", "😂  comedy_sketch"]
    cat_answer = inquirer.prompt([inquirer.List('cat', message="Choose a category", choices=cat_choices)])['cat']
    
    from app.ai_shorts.schemas import Category
    category_override = None
    if "kids" in cat_answer: category_override = Category.KIDS_FUN_STORY
    elif "horror" in cat_answer: category_override = Category.HORROR_SHORT
    elif "motivational" in cat_answer: category_override = Category.MOTIVATIONAL_STORY
    elif "comedy" in cat_answer: category_override = Category.COMEDY_SKETCH

    upload_ans = inquirer.prompt([inquirer.Confirm('upload', message="Upload to YouTube after generation?", default=False)])['upload']

    console.print("\n[bold yellow]Initializing AI Models...[/]")
    try:
        wf = AIShortsWorkflow()
        result = wf.run(category_override=category_override, upload_to_youtube=upload_ans)
        
        console.print(Panel(f"[bold green]✔ Generation Complete![/]\n\n[bold cyan]Saved to:[/] {result.video_path}\n[bold cyan]Title:[/] {result.title}\n[bold cyan]YouTube URL:[/] {result.youtube_url or 'Not uploaded'}", title="🎬 AI Short Result", border_style="green"))
    except Exception as e:
        console.print(f"[bold red]❌ AI Short Generation failed:[/] {e}")


def main_loop():
    while True:
        print_header()
        
        questions = [
            inquirer.List(
                'action',
                message="Select an execution step:",
                choices=[
                    "0. 🚀 START MASS DEPLOYMENT (Full Loop Auto) 🚀",
                    "1. Download YouTube Video API",
                    "2. Native Crop to Vertical (9:16)",
                    "3. OpenAi Whisper Transcribe Audio",
                    "4. Native FFmpeg Burn Captions",
                    "5. Generate AI Viral Metadata",
                    "6. 🎬 Generate Video from Prompt (Veo 3 + Audio)",
                    "7. 🤖 Generate AI Short (Local Pipeline)",
                    "❌ Exit"
                ],
            )
        ]
        
        answers = inquirer.prompt(questions)
        if not answers:
            break
            
        choice = answers['action']
        
        if choice.startswith("1"):
            step_download()
        elif choice.startswith("2"):
            step_crop()
        elif choice.startswith("3"):
            step_transcribe()
        elif choice.startswith("4"):
            step_burn_captions()
        elif choice.startswith("5"):
            step_ai_metadata()
        elif choice.startswith("6"):
            step_veo3_from_prompt()
        elif choice.startswith("7"):
            step_generate_ai_short()
        elif choice.startswith("0."):
            setup_q = [
                inquirer.Text("amount", message="How many shorts to process in this run?", default="1")
            ]
            ans = inquirer.prompt(setup_q)
            if not ans:
                continue
            
            try:
                amt = int(ans["amount"])
            except ValueError:
                amt = 1
                
            step_autonomous(limit=amt)
        else:
            console.print("[dim]Goodbye![/]")
            break
        
        console.input("\n[dim]Press Enter to return to the main menu...[/]")


if __name__ == "__main__":
    main_loop()
