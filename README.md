# Knot-Labs

A powerful, privacy-focused social media backend that puts you in control. Build your own social platform with intelligent content classification, personalized feed ranking, and full-text search - all running locally on your machine.

## What is Knot-Labs?

Knot-Labs is a complete social media stack that demonstrates how modern social platforms work under the hood. It includes everything you need to understand and experiment with:

- **Smart Media Classification** - Automatically understands what videos and images are about using AI
- **Personalized Feed Ranking** - Creates custom feeds based on user preferences and behavior
- **Content Discovery** - Full-text search across all posts and categories
- **Analytics Dashboard** - See what content is trending and how users interact

All of this runs entirely on your computer - no cloud services required, your data stays with you.

## Key Features

### 🎬 Intelligent Media Understanding

- Automatically categorizes videos and images into topics
- Understands content through video, speech, and audio analysis
- Creates multi-level tags (broad topics → subtopics → specific tags)

### 📊 Smart Feed Algorithm

- Personalized content ranking based on user preferences
- Balances engagement, freshness, and diversity
- Prevents repetitive content from the same creators

### 🔍 Powerful Search

- Find posts by keywords, descriptions, or categories
- Lightning-fast results with intelligent ranking
- Multiple search backends for different use cases

### 🎨 User-Friendly Interfaces

- **Web UI** - Modern browser-based interface
- **Desktop App** - Native GUI application for Windows/Mac/Linux
- **API** - RESTful endpoints for custom integrations
- **CLI** - Command-line tools for power users

## Quick Start

### Installation (5 minutes)

1. **Download the code**

   ```bash
   git clone https://github.com/yourusername/Knot-Labs.git
   cd Knot-Labs
   ```

2. **Run the setup** (choose one):

   **Windows (PowerShell):**

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
   ```

   **Mac/Linux:**

   ```bash
   bash scripts/setup.sh
   ```

3. **Start the system**

   ```bash
   # Windows
   scripts\start-api.bat

   # Mac/Linux
   bash scripts/start-api.sh
   ```

4. **Open your browser**

   Navigate to http://localhost:8000 - you'll see the Knot-Labs interface!

### Your First Steps

1. **Create a User** - Click "Create User" and give yourself a username
2. **Generate Content** - Use "Generate Posts" to create sample content
3. **Explore the Feed** - Click "Get Feed" to see personalized recommendations
4. **Try Searching** - Search for topics like "cats", "sports", or "technology"
5. **Upload Media** - Drop a video or image to see automatic classification in action

## Use Cases

### For Educators & Students

- Learn how social media algorithms work
- Understand content recommendation systems
- Explore AI-powered media classification
- Study data structures and APIs

### For Developers

- Prototype social features without cloud dependencies
- Test content moderation strategies
- Build custom social experiences
- Integrate with existing applications

### For Researchers

- Analyze recommendation algorithms
- Study content categorization systems
- Experiment with ranking strategies
- Test algorithmic transparency approaches

### For Privacy Advocates

- Run a completely local social platform
- Keep all data under your control
- No tracking, no surveillance
- Full transparency in how feeds are generated

## System Requirements

- **Operating System**: Windows 10+, macOS 10.15+, or Linux
- **Python**: Version 3.10 or newer
- **Memory**: 4GB RAM minimum (8GB recommended for video processing)
- **Storage**: 2GB free space
- **Optional**: GPU for faster media processing

## Features in Detail

### Media Classification

When you upload a video or image, Knot-Labs automatically:

- Identifies objects and scenes
- Transcribes speech to understand context
- Analyzes audio for music and sound events
- Generates hierarchical categories (e.g., Animals → Pets → Cats)

### Feed Personalization

The ranking system considers:

- What categories you interact with most
- How fresh the content is
- Creator diversity (avoiding repetition)
- Engagement signals (likes, comments, shares)
- Content quality indicators

### Search Capabilities

- **Text Search**: Find posts by keywords in titles and descriptions
- **Category Browse**: Explore content by topic hierarchies
- **Semantic Search**: Find similar content even with different wording
- **Filters**: Narrow results by date, creator, or engagement

## Configuration Options

Knot-Labs can be customized through environment variables:

- **API Security**: Add password protection with `KNOT_API_KEY`
- **Storage**: Connect MongoDB for persistent data storage
- **Caching**: Enable Redis for faster performance
- **CORS**: Allow access from other domains
- **Upload Limits**: Configure maximum file sizes

See [MANUAL.md](MANUAL.md) for detailed configuration instructions.

## Support & Documentation

- **User Guide**: This README
- **Developer Manual**: [MANUAL.md](MANUAL.md) - Technical documentation
- **API Reference**: http://localhost:8000/docs (when running)
- **WARP Guide**: [WARP.md](WARP.md) - For AI-assisted development

## Demo Videos & Screenshots

### Web Interface

The modern web UI provides easy access to all features:

- User and post creation
- Media upload with drag-and-drop
- Real-time classification results
- Interactive feed exploration

### Desktop Application

The native GUI offers:

- Dark/light theme support
- Category tree browser
- Batch content generation
- Advanced classification controls

### API Dashboard

FastAPI's built-in documentation at `/docs` shows:

- All available endpoints
- Interactive API testing
- Request/response schemas
- Authentication setup

## Privacy & Data

- **100% Local**: All processing happens on your machine
- **No External APIs**: No data sent to third parties
- **Transparent Algorithms**: All ranking logic is visible and modifiable
- **Data Portability**: Export/import your data anytime
- **No Tracking**: No analytics, telemetry, or user tracking

## License

MIT License - see [LICENSE](LICENSE) file for details.
