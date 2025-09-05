# Mesh

Mesh is a lightweight local database for the Knot!Labs. It stores users and posts as JSON files and updates engagement scores based on actions taken on the platform. A small CLI demo is included to create data and simulate engagement.

## Features
- Users stored in separate files under `Users/`
- Posts stored in batches of 500 under `Posts/`
- Storage paths are resolved relative to the project, so files always end up in
  the correct folders regardless of where the code is executed
- Engagement tracking for views, likes, comments, shares, and gifts
- Query interface for filtering and ranking
- Ranking to surface top categories by engagement
- Interactive demo script for manual testing
- Commands to generate sample data and simulate random engagement

## Running the demo
```bash
python demo.py
```
Follow the on-screen menu to create users, create posts, record engagement, list data, run queries, generate sample data, or simulate random engagement.

## Data schema
### User
```json
{
  "userID": "string",
  "Gender": "string",
  "SeenPosts": ["postID"],
  "CreatorScore": 0,
  "ViewerScore": {"creatorID": points},
  "created_at": 1680000000.0
}
```
`AccountAge` is calculated on load from `created_at` and is not stored.

### Post
```json
{
  "postID": "string",
  "creator": "userID",
  "Score": 0,
  "like_number": 0,
  "comment_number": 0,
  "share_number": 0,
  "Categories": ["sports"],
  "created_at": 1680000000.0
}
```
`Age` is calculated on load and is not stored.

## Example usage
1. **Create a user**
   - Option 1 in the menu, provide userID and gender.
2. **Create a post**
   - Option 2, provide postID, creator userID, and categories.
3. **Record engagement**
   - Option 3, specify acting user, postID, action, and optional gift amount.
4. **Query**
   - Option 4, enter queries like:
     - `type:user gender:male limit:5`
     - `type:post category:sports sort:score order:desc limit:10`
     - `top:creators limit:5`
     - `top:posts limit:5`
     - `top:categories`
5. **Generate sample data**
   - Option 7, choose how many users and posts to create automatically.
6. **Simulate engagement**
   - Option 8, choose how many random engagement events to run.

User files live in `Users/`, while posts are grouped into files of up to 500 posts inside `Posts/`.
