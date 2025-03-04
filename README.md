# Telegram Group & Channel Manager

A simple GUI application that lets you leave Telegram groups and channels in bulk while keeping the ones you select.

## Features

- Leave multiple groups/channels at once
- Select which groups/channels to keep
- Search and filter to find specific groups
- Sort groups by name or ID
- Works with regular groups, supergroups, and channels

## Requirements

- Python 3.6+
- PyQt5
- Telethon
- Telegram API credentials from https://my.telegram.org

## Installation

```
pip install telethon pyqt5
```

## How to Use

1. Get your API ID and Hash from https://my.telegram.org
2. Run the script: `python telegram_group_manager.py`
3. Enter your API credentials and phone number
4. Click "Connect & Fetch Groups/Channels"
5. Check the boxes for groups you want to KEEP
6. Click "Leave Unselected Groups"

## Notes

- Your credentials are saved locally for convenience
- The app creates log files of all operations
