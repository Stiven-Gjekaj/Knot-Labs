import json
import os
import tempfile
import time
from os import PathLike
from typing import Any, Dict, List


class MeshStore:
    """Simple file-based storage for users and posts."""

    def __init__(self, base_path: str | PathLike[str] | None = None) -> None:
        """Create a store rooted at *base_path*.

        If *base_path* is ``None`` the directory containing this module is
        used. The ``Users`` and ``Posts`` folders will be created if they don't
        already exist.
        """
        if base_path is None:
            base_path = os.path.dirname(os.path.abspath(__file__))
        self.user_path = os.path.join(base_path, 'Users')
        self.post_path = os.path.join(base_path, 'Posts')
        os.makedirs(self.user_path, exist_ok=True)
        os.makedirs(self.post_path, exist_ok=True)

    # --- helpers ---------------------------------------------------------
    def _atomic_write(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON atomically to avoid partial files."""
        directory = os.path.dirname(path)
        fd, tmp_path = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd, 'w') as tmp:
                json.dump(data, tmp, indent=2)
            try:
                os.replace(tmp_path, path)
            except PermissionError:
                if os.path.exists(path):
                    os.remove(path)
                os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _hours_since(self, ts: float) -> float:
        """Return hours since timestamp."""
        return (time.time() - ts) / 3600.0

    # --- user helpers ----------------------------------------------------
    def _user_files(self) -> List[str]:
        files = [f for f in os.listdir(self.user_path) if f.endswith('.json')]
        files.sort()
        return [os.path.join(self.user_path, f) for f in files]

    def _find_user_file(self, user_id: str) -> tuple[str | None, Dict[str, Any] | None]:
        for path in self._user_files():
            with open(path, 'r') as f:
                data = json.load(f)
            if user_id in data:
                return path, data
        return None, None

    # --- user methods ----------------------------------------------------
    def save_user(self, user: Dict[str, Any]) -> None:
        """Persist user data."""
        data = user.copy()
        data.pop('AccountAge', None)  # computed field

        path, users_data = self._find_user_file(user['userID'])
        if path and users_data is not None:
            users_data[user['userID']] = data
            self._atomic_write(path, users_data)
            return

        files = self._user_files()
        if files:
            path = files[-1]
            with open(path, 'r') as f:
                users_data = json.load(f)
            if len(users_data) >= 50:
                index = len(files) + 1
                path = os.path.join(self.user_path, f"users_{index:04d}.json")
                users_data = {}
        else:
            path = os.path.join(self.user_path, "users_0001.json")
            users_data = {}

        users_data[user['userID']] = data
        self._atomic_write(path, users_data)

    def load_user(self, user_id: str) -> Dict[str, Any]:
        """Load user and attach AccountAge."""
        path, users_data = self._find_user_file(user_id)
        if not path or users_data is None:
            raise FileNotFoundError(f"User {user_id} not found")
        data = users_data[user_id]
        result = data.copy()
        result['AccountAge'] = self._hours_since(data.get('created_at', time.time()))
        return result

    def list_users(self) -> List[Dict[str, Any]]:
        users: List[Dict[str, Any]] = []
        for path in self._user_files():
            with open(path, 'r') as f:
                data = json.load(f)
            for uid, udata in data.items():
                item = udata.copy()
                item['userID'] = uid
                item['AccountAge'] = self._hours_since(
                    udata.get('created_at', time.time())
                )
                users.append(item)
        return users

    # --- post methods ----------------------------------------------------
    # --- post helpers ----------------------------------------------------
    def _post_files(self) -> List[str]:
        files = [f for f in os.listdir(self.post_path) if f.endswith('.json')]
        files.sort()
        return [os.path.join(self.post_path, f) for f in files]

    def _find_post_file(self, post_id: str) -> tuple[str | None, Dict[str, Any] | None]:
        for path in self._post_files():
            with open(path, 'r') as f:
                data = json.load(f)
            if post_id in data:
                return path, data
        return None, None

    def save_post(self, post: Dict[str, Any]) -> None:
        data = post.copy()
        data.pop('Age', None)
        path, posts_data = self._find_post_file(post['postID'])
        if path and posts_data is not None:
            posts_data[post['postID']] = data
            self._atomic_write(path, posts_data)
            return
        files = self._post_files()
        if files:
            path = files[-1]
            with open(path, 'r') as f:
                posts_data = json.load(f)
            if len(posts_data) >= 500:
                index = len(files) + 1
                path = os.path.join(self.post_path, f"posts_{index:04d}.json")
                posts_data = {}
        else:
            path = os.path.join(self.post_path, "posts_0001.json")
            posts_data = {}
        posts_data[post['postID']] = data
        self._atomic_write(path, posts_data)

    def load_post(self, post_id: str) -> Dict[str, Any]:
        path, posts_data = self._find_post_file(post_id)
        if not path or posts_data is None:
            raise FileNotFoundError(f"Post {post_id} not found")
        data = posts_data[post_id]
        result = data.copy()
        result['Age'] = self._hours_since(data.get('created_at', time.time()))
        return result

    def list_posts(self) -> List[Dict[str, Any]]:
        posts: List[Dict[str, Any]] = []
        for path in self._post_files():
            with open(path, 'r') as f:
                data = json.load(f)
            for pid, pdata in data.items():
                item = pdata.copy()
                item['postID'] = pid
                item['Age'] = self._hours_since(pdata.get('created_at', time.time()))
                posts.append(item)
        return posts


class MeshDB:
    """High level interface for Mesh."""

    POINTS = {
        'view_full': 1,
        'like': 1,
        'comment': 2,
        'share': 3,
    }

    def __init__(self, store: MeshStore | None = None) -> None:
        self.store = store or MeshStore()

    # --- creation --------------------------------------------------------
    def create_user(self, user_id: str, gender: str) -> Dict[str, Any]:
        user = {
            'userID': user_id,
            'Gender': gender,
            'SeenPosts': [],
            'CreatorScore': 0,
            'ViewerScore': {},
            'CategoryScores': {},
            'created_at': time.time(),
        }
        self.store.save_user(user)
        return user

    def create_post(self, post_id: str, creator: str, categories: List[str]) -> Dict[str, Any]:
        post = {
            'postID': post_id,
            'creator': creator,
            'Score': 0,
            'like_number': 0,
            'comment_number': 0,
            'share_number': 0,
            'gift_number': 0,
            'Categories': categories[:3],
            'created_at': time.time(),
        }
        self.store.save_post(post)
        return post

    # --- engagement ------------------------------------------------------
    def record_engagement(self, user_id: str, post_id: str, action: str, gift_amount: int = 0) -> None:
        user = self.store.load_user(user_id)
        post = self.store.load_post(post_id)
        creator = self.store.load_user(post['creator'])

        if action == 'gift':
            post['gift_number'] += 1
            points = gift_amount
        else:
            points = self.POINTS.get(action, 0)

        if action == 'like':
            post['like_number'] += 1
        elif action == 'comment':
            post['comment_number'] += 1
        elif action == 'share':
            post['share_number'] += 1

        post['Score'] += points
        creator['CreatorScore'] += points

        viewer_score = user['ViewerScore'].get(post['creator'], 0)
        user['ViewerScore'][post['creator']] = viewer_score + points
        if post_id not in user['SeenPosts']:
            user['SeenPosts'].append(post_id)

        cat_scores = user.get('CategoryScores', {})
        for cat in post['Categories']:
            cat_scores[cat] = cat_scores.get(cat, 0) + points
        user['CategoryScores'] = cat_scores

        self.store.save_post(post)
        self.store.save_user(user)
        if creator['userID'] != user_id:
            self.store.save_user(creator)

    # --- queries ---------------------------------------------------------
    def query(self, prompt: str) -> List[Dict[str, Any]]:
        parts = prompt.split()
        params: Dict[str, str] = {}
        for part in parts:
            if ':' in part:
                key, val = part.split(':', 1)
                params[key] = val

        limit = int(params.get('limit', '10'))
        order = params.get('order', 'asc')
        reverse = order == 'desc'

        if 'top' in params:
            if params['top'] == 'creators':
                users = self.store.list_users()
                users.sort(key=lambda u: u['CreatorScore'], reverse=True)
                return users[:limit]
            if params['top'] == 'posts':
                posts = self.store.list_posts()
                posts.sort(key=lambda p: p['Score'], reverse=True)
                return posts[:limit]
            if params['top'] == 'categories':
                limit = int(params.get('limit', '3'))
                posts = self.store.list_posts()
                cat_scores: Dict[str, int] = {}
                for p in posts:
                    for c in p['Categories']:
                        cat_scores[c] = cat_scores.get(c, 0) + p['Score']
                categories = [
                    {'Category': name, 'Score': score}
                    for name, score in cat_scores.items()
                ]
                categories.sort(key=lambda c: c['Score'], reverse=True)
                return categories[:limit]

        if params.get('type') == 'user':
            users = self.store.list_users()
            gender = params.get('gender')
            if gender:
                users = [u for u in users if u['Gender'] == gender]
            sort_key = params.get('sort')
            if sort_key == 'creatorScore':
                users.sort(key=lambda u: u['CreatorScore'], reverse=reverse)
            return users[:limit]

        if params.get('type') == 'post':
            posts = self.store.list_posts()
            category = params.get('category')
            if category:
                posts = [p for p in posts if category in p['Categories']]
            sort_key = params.get('sort')
            if sort_key == 'score':
                posts.sort(key=lambda p: p['Score'], reverse=reverse)
            return posts[:limit]

        return []
