
import requests,json,subprocess,shutil
import m3u8,zipfile,os,re,math
from Crypto.Cipher import AES
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from IPython.display import clear_output
from requests.exceptions import SSLError, ConnectionError, RequestException



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




def merge_videos_with_ffmpeg(output_videos_folder, final_output_file, max_per_merge=6):
    """
    Merges videos named file_{num}.mp4 from a folder into one or more video files using FFmpeg.

    Args:
        output_videos_folder (str): Path to the folder containing video segments.
        final_output_file (str): Base name for the output (e.g., 'final_video.mp4').
        max_per_merge (int): Maximum number of video files per merged part.
    """
    print(f"📂 Looking for video parts in: {output_videos_folder}")
    
    # Step 1: Collect and sort video files
    video_files = [
        f for f in os.listdir(output_videos_folder)
        if re.match(r'file_(\d+)\.mp4$', f)
    ]

    if not video_files:
        print("⚠️ No video files found to merge.")
        return

    # Sort files numerically
    video_files.sort(key=lambda x: int(re.search(r'file_(\d+)\.mp4$', x).group(1)))
    print(f"📑 Sorted video files: {len(video_files)}")

    # Step 2: Split files into chunks of `max_per_merge`
    num_parts = math.ceil(len(video_files) / max_per_merge)
    base_name = os.path.splitext(final_output_file)[0]

    for i in range(num_parts):
        part_files = video_files[i * max_per_merge : (i + 1) * max_per_merge]
        part_name = f"{base_name}_part_{i + 1}.mp4"

        # Create list file for ffmpeg
        list_file_path = os.path.join(output_videos_folder, f'videos_to_merge_{i + 1}.txt')
        with open(list_file_path, 'w') as list_file:
            for vf in part_files:
                list_file.write(f"file '{vf}'\n")

        # Merge using FFmpeg
        print(f"🛠️ Merging part {i + 1} into '{part_name}'...")
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", f"videos_to_merge_{i + 1}.txt",
            "-c", "copy", os.path.join("/content/output_folder", part_name)
        ]
        subprocess.run(cmd, check=True, cwd=output_videos_folder)

    print(f"✅ All parts merged successfully into {num_parts} file(s).")


def download_decrypt_merge(title, m3u8_file='video.m3u8'):
    print(f"📥 Processing M3U8: {m3u8_file}")

    try:
        # Step 1: Load the m3u8 file
        playlist = m3u8.load(m3u8_file)

        # Step 2: Get AES-128 Key
        key_uri = playlist.keys[0].uri
        key_response = requests.get(key_uri, headers=headers, timeout=10)
        key_response.raise_for_status()
        key = key_response.content

        # Step 3: Download and Decrypt Segments in Parallel
        def download_and_decrypt(segment, retries=3):
            for attempt in range(retries):
                try:
                    segment_url = segment.uri
                    response = requests.get(segment_url, headers=headers, timeout=10, stream=True)
                    response.raise_for_status()
                    encrypted_data = response.content
                    cipher = AES.new(key, AES.MODE_CBC, iv=key)
                    return cipher.decrypt(encrypted_data)
                except (SSLError, ConnectionError, RequestException) as e:
                    print(f"⚠️ Retry {attempt+1} failed for segment: {segment.uri} - {type(e).__name__}: {e}")
            print(f"❌ Skipped segment after {retries} failed attempts: {segment.uri}")
            return b""

        print("⏳ Downloading and decrypting segments...")
        with ThreadPoolExecutor(max_workers=50) as executor:
            decrypted_segments = list(tqdm(executor.map(download_and_decrypt, playlist.segments), total=len(playlist.segments)))

        # Remove failed (empty) segments
        decrypted_segments = [seg for seg in decrypted_segments if seg]

        if not decrypted_segments:
            print("❌ No segments downloaded. Skipping file.")
            return False
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(title), exist_ok=True)


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
        print(f"❌ Error while processing '{title}': {type(e).__name__}: {e}")
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


    # List files inside json_files folder
    json_files_lst = os.listdir(json_folder_name)
    print(f"📁 JSON files found: {len(json_files_lst)}")

    data = None

    # Check if JSON files exist
    if len(json_files_lst) > 0:
        for json_file in json_files_lst[json_start:json_end]:
            os.makedirs(output_videos_folder,exist_ok=True)
             
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
            
