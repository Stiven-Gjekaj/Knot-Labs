import random

from mesh_db import MeshDB, MeshStore


def user_summary(user: dict) -> str:
    return (
        f"User {user['userID']} | Gender: {user['Gender']} | "
        f"CreatorScore: {user['CreatorScore']} | "
        f"AccountAge: {user['AccountAge']:.1f}h"
    )


def post_summary(post: dict) -> str:
    cats = ', '.join(post['Categories'])
    return (
        f"Post {post['postID']} by {post['creator']} | Score: {post['Score']} | "
        f"Age: {post['Age']:.1f}h | Categories: {cats}"
    )


def generate_sample_data(db: MeshDB, num_users: int = 5, num_posts: int = 20) -> None:
    """Populate the database with sample users and posts."""
    genders = ["male", "female", "other"]
    categories = ["sports", "news", "tech", "music", "fashion"]
    users = []
    for i in range(1, num_users + 1):
        user_id = f"user{i}"
        user = db.create_user(user_id, random.choice(genders))
        users.append(user)
    for i in range(1, num_posts + 1):
        post_id = f"post{i}"
        creator = random.choice(users)["userID"]
        cats = random.sample(categories, k=random.randint(1, 3))
        db.create_post(post_id, creator, cats)


def simulate_random_engagement(db: MeshDB, events: int = 50) -> None:
    """Simulate random engagement events between users and posts."""
    actions = ["view_full", "like", "comment", "share"]
    users = db.store.list_users()
    posts = db.store.list_posts()
    if not users or not posts:
        return
    for _ in range(events):
        user = random.choice(users)["userID"]
        post = random.choice(posts)["postID"]
        action = random.choice(actions)
        db.record_engagement(user, post, action)


def main() -> None:
    db = MeshDB(MeshStore())

    MENU = (
        "\nMesh Demo\n"
        "1. Create user\n"
        "2. Create post\n"
        "3. Record engagement\n"
        "4. Query database\n"
        "5. List users\n"
        "6. List posts\n"
        "7. Generate sample data\n"
        "8. Simulate random engagement\n"
        "0. Exit\nChoice: "
    )

    while True:
        choice = input(MENU).strip()

        if choice == '1':
            user_id = input('UserID: ').strip()
            gender = input('Gender: ').strip()
            db.create_user(user_id, gender)
            print('User created.')

        elif choice == '2':
            post_id = input('PostID: ').strip()
            creator = input('Creator userID: ').strip()
            cats = input('Categories (comma separated, max 3): ').split(',')
            categories = [c.strip() for c in cats if c.strip()][:3]
            db.create_post(post_id, creator, categories)
            print('Post created.')

        elif choice == '3':
            user_id = input('Acting userID: ').strip()
            post_id = input('PostID: ').strip()
            action = input('Action (view_full/like/comment/share/gift): ').strip()
            gift_amount = 0
            if action == 'gift':
                gift_amount = int(input('Gift amount: ').strip() or '0')
            db.record_engagement(user_id, post_id, action, gift_amount)
            print('Engagement recorded.')

        elif choice == '4':
            prompt = input('Query: ').strip()
            results = db.query(prompt)
            for item in results:
                if 'userID' in item:
                    print(user_summary(item))
                elif 'postID' in item:
                    print(post_summary(item))
                elif 'Category' in item:
                    print(f"Category {item['Category']} | Total Score: {item['Score']}")

        elif choice == '5':
            for user in db.store.list_users():
                print(user_summary(user))

        elif choice == '6':
            for post in db.store.list_posts():
                print(post_summary(post))

        elif choice == '7':
            num_users = int(input('How many users? (default 5): ').strip() or '5')
            num_posts = int(input('How many posts? (default 20): ').strip() or '20')
            generate_sample_data(db, num_users, num_posts)
            print('Sample data generated.')

        elif choice == '8':
            events = int(input('How many events? (default 50): ').strip() or '50')
            simulate_random_engagement(db, events)
            print('Random engagement simulated.')

        elif choice == '0':
            break
        else:
            print('Invalid choice.')


if __name__ == '__main__':
    main()
