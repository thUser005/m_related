
import requests,json,subprocess,shutil
import m3u8,zipfile,os,re
from Crypto.Cipher import AES
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from IPython.display import clear_output
from requests.exceptions import SSLError, ConnectionError


# Headers to bypass protection
headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9,te;q=0.8,hi;q=0.7",
    "cache-control": "no-cache",
    "origin": "https://www.miruro.tv",
    "pragma": "no-cache",
    "referer": "https://www.miruro.tv/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
}

def unzip_file(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)


def merge_videos_with_ffmpeg(output_videos_folder, final_output_file):
    """
    Merges all videos named file_{num}.mp4 from a folder into a single video file using FFmpeg.

    Args:
        output_videos_folder (str): Path to the folder containing video segments.
        final_output_file (str): Name of the final output video (e.g., 'final_video.mp4').
    """
    print(f"📂 Looking for video parts in: {output_videos_folder}")
    
    # Step 1: Collect and sort video files by number
    video_files = [
        f for f in os.listdir(output_videos_folder)
        if re.match(r'file_(\d+)\.mp4$', f)
    ]

    if not video_files:
        print("⚠️ No video files found to merge.")
        return

    # Sort files by extracted number
    video_files.sort(key=lambda x: int(re.search(r'file_(\d+)\.mp4$', x).group(1)))
    
    print(f"📑 Sorted video files: {video_files}")

    # Step 2: Create FFmpeg file list
    list_file_path = os.path.join(output_videos_folder, 'videos_to_merge.txt')
    with open(list_file_path, 'w') as list_file:
        for vf in video_files:
            list_file.write(f"file '{vf}'\n")  # Just the filename, not path like video_files/file_1.mp4

    # Step 3: Run FFmpeg command
    print("🛠️ Merging videos using FFmpeg...")
    cmd =[
    "ffmpeg", "-f", "concat", "-safe", "0", "-i", "videos_to_merge.txt",
    "-c", "copy", f"/content/output_folder/{final_output_file}"
]
    subprocess.run(cmd, check=True, cwd="video_files")
    
    print(f"✅ Merge complete. Output saved as: {final_output_file}")


def download_decrypt_merge(title, m3u8_file='video.m3u8'):
    """
    Downloads and decrypts .ts video segments from an M3U8 playlist and merges them into a single MP4 file.
    """
    print(f"📥 Processing M3U8: {m3u8_file}")

    try:
        # Step 1: Load the m3u8 file
        playlist = m3u8.load(m3u8_file)

        # Step 2: Get AES-128 Key
        key_uri = playlist.keys[0].uri
        key_response = requests.get(key_uri, headers=headers)
        key = key_response.content

        # Step 3: Download and Decrypt Segments in Parallel
        def download_and_decrypt(segment, retries=3):
            for attempt in range(retries):
                try:
                    segment_url = segment.uri
                    response = requests.get(segment_url, headers=headers, timeout=10)
                    response.raise_for_status()
                    cipher = AES.new(key, AES.MODE_CBC, iv=key)
                    return cipher.decrypt(response.content)
                except (SSLError, ConnectionError, requests.RequestException) as e:
                    print(f"⚠️ Retry {attempt+1} failed for segment: {segment.uri}")
            print(f"❌ Skipped segment after {retries} failed attempts: {segment.uri}")
            return b""

        print("⏳ Downloading and decrypting segments...")
        with ThreadPoolExecutor(max_workers=20) as executor:
            decrypted_segments = list(tqdm(executor.map(download_and_decrypt, playlist.segments), total=len(playlist.segments)))

        # Remove failed (empty) segments
        decrypted_segments = [seg for seg in decrypted_segments if seg]

        if not decrypted_segments:
            print("❌ No segments downloaded. Skipping file.")
            return False

        # Step 4: Merge all decrypted segments into one file
        ts_file = f"{title}.ts"
        with open(ts_file, 'wb') as final_file:
            for segment in decrypted_segments:
                final_file.write(segment)

        # Step 5: Rename the final file to .mp4
        mp4_file = f"{title}"
        os.rename(ts_file, mp4_file)

        # Step 6: Cleanup
        if os.path.exists(mp4_file):
            if os.path.exists(m3u8_file):
                os.remove(m3u8_file)
            if os.path.exists(ts_file):
                os.remove(ts_file)
            print("🧹 Temporary files cleaned up.")

        print(f"✅ Done! Video saved as '{mp4_file}'.")
        return True

    except Exception as e:
        print(f"❌ Error while processing '{title}': {e}")
        return False

def download_m3u8(url, filename="video.m3u8"):
    """
    Downloads an .m3u8 playlist file from the provided URL and saves it locally.

    Args:
        url (str): The m3u8 URL.
        filename (str): The output filename (default is 'video.m3u8').
    """
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9,te;q=0.8,hi;q=0.7",
        "cache-control": "no-cache",
        "origin": "https://www.miruro.tv",
        "pragma": "no-cache",
        "referer": "https://www.miruro.tv/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    }

    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Raise an error for bad status codes

        with open(filename, 'w', encoding='utf-8') as file:
            file.write(response.text)

        print(f"✅ '{filename}' downloaded successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to download m3u8 file: {e}")


def main(json_start,json_end):
        
    # List all files in current directory
    all_files = os.listdir()
    json_folder_name = 'json_files'

    # Unzip if necessary
    if json_folder_name not in all_files and 'json_zipped.zip' in all_files:
        print("📦 'json_files' folder not found. Unzipping 'json_zipped.zip'...")
        unzip_file("json_zipped.zip", json_folder_name)
        print("✅ Unzipping completed.")

    output_videos_folder = "video_files"

    os.makedirs(output_videos_folder,exist_ok=True)

    # List files inside json_files folder
    json_files_lst = os.listdir(json_folder_name)
    print(f"📁 JSON files found: {len(json_files_lst)}")

    data = None

    # Check if JSON files exist
    if len(json_files_lst) > 0:
        for json_file in json_files_lst[json_start:json_end]:
                
            json_file_path = f"./{json_folder_name}/{json_file}"
            print(f"📄 Loading JSON data from: {json_file_path}")
            
            with open(json_file_path, encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Loaded {len(data)} entries from {json_file}")

            # Process each video entry
            if data:
                for index, video_data in enumerate(data):
                    print(30*"--")
                    print(f"\n🔄 Processing {index + 1}/{len(data)}")

                    video_num = video_data.get('episode')
                    url = video_data.get('video_url')
                    
                    if not url:
                        print(f"⚠️ Skipping episode {video_num}: No video URL provided.")
                        continue
                    
                    if "m3u8/?url" not in url:
                        print(f"⚠️ Skipping episode {video_num}: URL format not supported.")
                        continue

                    print(f"🌐 Downloading M3U8 from: {url}")
                    video_flag = download_m3u8(url)

                    if video_flag:
                        output_video_file = f"./{output_videos_folder}/file_{video_num}.mp4"
                        print(f"⬇️ Downloading and decrypting video as '{output_video_file}'...")
                        download_decrypt_merge(output_video_file)
                    else:
                        print(f"❌ Failed to download M3U8 for episode {video_num}")

                if len(output_videos_folder)>0:
                    print("videos merged started..")
                    final_video = f"{json_file.split('.')[0]}.mp4"
                    merge_videos_with_ffmpeg(output_videos_folder,final_video)
                    clear_output(wait=True)
                    print("Removing videos folder..")
                    shutil.rmtree(output_videos_folder)
                    
            else:
                
                print("🚫 No JSON data to process.")
            
