# Daily SEO Feed (Bluesky)

A custom feed generator for Bluesky that surfaces high-quality SEO content based on expert engagement. Built with Python using the AT Protocol SDK.

## Features

- Custom algorithm tracking engagement from verified SEO experts
- Weighted scoring system for likes, reposts, and comments
- Time-decay factor for content freshness
- MySQL database for efficient data storage
- Web interface to view current feed content
- Configurable engagement thresholds and weights
- Automatic cleanup of outdated content

## Requirements

- Python 3.9+
- MySQL Database
- Bluesky account for feed publication

## Setup

1. Clone the repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
   - Copy `.env-prod` to `.env`
   - Update the database credentials
   - Set your `FEEDGEN_HOSTNAME`

4. Initialize the database:
```bash
python -m server --rebuild_database
```

5. Publish your feed:
```bash
python publish_feed.py
```

6. Update your `.env` with the generated feed URI

## Running the Service

There are several ways to run the service based on your needs:

### Full Service Mode
Run both the API server and Jetstream processor together:
```bash
python -m server
```

### Component Separation
You can run components separately:

#### API Server Only
Run just the web API and interface:
```bash
python -m server --app_only
```

#### Jetstream Processor Only
Run just the data processing component:
```bash
python -m server --jetstream_only
```

### Development Mode
Run with debug logging enabled:
```bash
python -m server --debug
```

## Endpoints

- `/.well-known/did.json` - DID document
- `/xrpc/app.bsky.feed.describeFeedGenerator` - Feed metadata
- `/xrpc/app.bsky.feed.getFeedSkeleton` - Feed content
- `/health` - Service health check
- `/` - Web interface showing current feed content

## Customization

- Adjust scoring weights in `.env`
- Modify `user_list.txt` to update tracked experts
- Configure post lifetime and minimum engagement score

## License

MIT