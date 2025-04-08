
import requests,json
import m3u8
from Crypto.Cipher import AES
from tqdm import tqdm
import os
from concurrent.futures import ThreadPoolExecutor
import zipfile


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

def download_decrypt_merge(title, m3u8_file='video.m3u8'):
    """
    Downloads and decrypts .ts video segments from an M3U8 playlist and merges them into a single MP4 file.

    Args:
        title (str or int): The filename (without extension) for the final .mp4 file.
        m3u8_file (str): Path to the downloaded M3U8 file.
    """
    print(f"📥 Processing M3U8: {m3u8_file}")

    # Step 1: Load the m3u8 file
    playlist = m3u8.load(m3u8_file)

    # Step 2: Get AES-128 Key
    key_uri = playlist.keys[0].uri
    key_response = requests.get(key_uri, headers=headers)
    key = key_response.content

    # Step 3: Download and Decrypt Segments in Parallel
    def download_and_decrypt(segment):
        segment_url = segment.uri
        segment_data = requests.get(segment_url, headers=headers).content
        cipher = AES.new(key, AES.MODE_CBC, iv=key)
        decrypted_data = cipher.decrypt(segment_data)
        return decrypted_data

    print("⏳ Downloading and decrypting segments...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        decrypted_segments = list(tqdm(executor.map(download_and_decrypt, playlist.segments), total=len(playlist.segments)))

    # Step 4: Merge all decrypted segments into one file
    ts_file = f"{title}.ts"
    with open(ts_file, 'wb') as final_file:
        for segment in decrypted_segments:
            final_file.write(segment)

    # Step 5: Rename the final file to .mp4
    mp4_file = f"{title}.mp4"
    os.rename(ts_file, mp4_file)

    # Step 6: Cleanup if output file exists
    if os.path.exists(mp4_file):
        if os.path.exists(m3u8_file):
            os.remove(m3u8_file)
        if os.path.exists(ts_file):
            os.remove(ts_file)
        print("🧹 Temporary files cleaned up.")

    print(f"✅ Done! Video saved as '{mp4_file}'.")

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
print(f"📁 JSON files found: {json_files_lst}")

file_num = 0
data = None

# Check if JSON files exist
if len(json_files_lst) > 0:
    json_file = json_files_lst[file_num]
    json_file_path = f"./{json_folder_name}/{json_file}"
    print(f"📄 Loading JSON data from: {json_file_path}")
    
    with open(json_file_path, encoding='utf-8') as f:
        data = json.load(f)
        data = data[:2]
        print(f"✅ Loaded {len(data)} entries from {json_file}")

# Process each video entry
if data:
    for index, video_data in enumerate(data):
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
            output_video_file = f"./{output_videos_folder}file_{video_num}.mp4"
            print(f"⬇️ Downloading and decrypting video as '{output_video_file}'...")
            download_decrypt_merge(output_video_file)
        else:
            print(f"❌ Failed to download M3U8 for episode {video_num}")
else:
    print("🚫 No JSON data to process.")
