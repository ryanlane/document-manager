# Adding Folders to Archive Brain

Archive Brain runs in Docker containers, so folders from your host system need to be "mounted" (made accessible) to the containers before they can be indexed.

## Quick Start

1. **Edit docker-compose.yml**
2. **Add volume lines** to both `api` and `worker` services
3. **Restart containers** with `docker compose -f docker-compose.yml --profile prod up -d`

4. **Select folders** in the web UI under Settings → Sources

<p align="center">
  <img src="images/ab-settings.png" alt="Archive Brain Settings UI" width="600" />
  <br><em>Settings: add or remove source folders and configure LLMs</em>
</p>

## Volume Mount Syntax

```yaml
- /path/on/host:/data/archive/name-in-container
```

- **Left side**: The actual path on your computer
- **Right side**: Where it appears inside the container (must start with `/data/archive/`)

## Examples

### Local Folder

Mount a folder from your home directory:

```yaml
services:
  api:
    volumes:
      - ./archive_root:/data/archive
      - /home/username/Documents:/data/archive/documents    # ← Add this

  worker:
    volumes:
      - ./archive_root:/data/archive
      - /home/username/Documents:/data/archive/documents    # ← Same here
```

### External USB Drive

Mount an external drive (common on Linux):

```yaml
services:
  api:
    volumes:
      - ./archive_root:/data/archive
      - /media/username/MyDrive:/data/archive/external-drive

  worker:
    volumes:
      - ./archive_root:/data/archive
      - /media/username/MyDrive:/data/archive/external-drive
```

### Network Share (NFS)

First, mount the NFS share on your host system, then add it:

```bash
# On your host (one-time setup)
sudo mount -t nfs 192.168.1.100:/share /mnt/nas
```

```yaml
services:
  api:
    volumes:
      - ./archive_root:/data/archive
      - /mnt/nas:/data/archive/nas-files

  worker:
    volumes:
      - ./archive_root:/data/archive
      - /mnt/nas:/data/archive/nas-files
```

### Windows with WSL2

When running Docker Desktop with WSL2:

```yaml
services:
  api:
    volumes:
      - ./archive_root:/data/archive
      - /mnt/c/Users/YourName/Documents:/data/archive/my-docs
      - /mnt/d/Files:/data/archive/d-drive

  worker:
    volumes:
      - ./archive_root:/data/archive
      - /mnt/c/Users/YourName/Documents:/data/archive/my-docs
      - /mnt/d/Files:/data/archive/d-drive
```

## Complete Example

Here's a full docker-compose.yml snippet with multiple volumes:

```yaml
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./archive_root:/data/archive
      - /home/user/Documents:/data/archive/documents
      - /mnt/external-drive:/data/archive/external
      - /mnt/nas/photos:/data/archive/photos
    # ... rest of config

  worker:
    build: ./backend
    volumes:
      - ./archive_root:/data/archive
      - /home/user/Documents:/data/archive/documents
      - /mnt/external-drive:/data/archive/external
      - /mnt/nas/photos:/data/archive/photos
    # ... rest of config
```

## After Adding Volumes

1. **Restart Docker**:
   ```bash
   docker compose down
  docker compose -f docker-compose.yml --profile prod up -d
   ```

2. **Open Settings → Sources** in the web UI

3. **Click the + button** next to your new folder to start indexing

## Troubleshooting

### Folder doesn't appear

- Make sure the path on the left side exists
- Check file permissions (Docker needs read access)
- Restart containers after editing docker-compose.yml

### Permission denied errors

On Linux, you may need to add your user to the docker group or use `chmod` to adjust permissions:

```bash
sudo chmod -R o+r /path/to/folder
```

### Network share issues

- Ensure the share is mounted on the host before starting Docker
- Consider adding the mount to `/etc/fstab` for automatic mounting
- For SMB/CIFS shares, use `cifs-utils` package

### Large archives (100k+ files)

For very large archives:
- Start with "Fast Scan" indexing mode
- Add folders one at a time
- Monitor disk space and memory usage

## Best Practices

1. **Use descriptive names** for the container path (e.g., `/data/archive/work-projects`)
2. **Mount read-only** if you don't need writes: `/host/path:/data/archive/name:ro`
3. **Add both services** - API needs access for browsing, Worker needs it for processing
4. **Test with a small folder first** before adding large archives

## Need Help?

- Check the logs: `docker compose logs worker`
- Open an issue on GitHub
- Visit the project documentation
