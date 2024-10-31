from util.imports import *
from util.config import *

app = Flask(__name__)
CORS(app)
# app.config.from_pyfile("settings.py")

# config.py
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
MAIL_USERNAME = 'myprojectstesting2000@gmail.com'
MAIL_PASSWORD = 'Testing@Projects@TempEmail'
MAIL_DEFAULT_SENDER = 'myprojectstesting2000@gmail.com'

mail = Mail(app)

BASE_URL = "http://localhost:5000"


def schedule_price_drop_alert():
    try:
        users = db_session.query(models.Users)
        for user in users:
            payload = {"username": user.username}
            r = requests.post(f"{BASE_URL}/api/price-drop-alert", json=payload)
            print(r.text)
    except Exception as e:
        print(f"Error sending price drop alert: {e}")


scheduler = BackgroundScheduler()
scheduler.add_job(func=schedule_price_drop_alert, trigger="interval", seconds=180)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


@app.route("/")
def index():
    return "Scheduler is running!"


@app.route("/postings/<username>", methods=["GET"])
def get_postings(username):
    validation1 = (
        db_session.query(models.Users).filter(models.Users.username == username).first()
    )
    if validation1 is None:
        return jsonify(
            content={"status": "error", "message": f"User {username} does not exist"}
        )
    products = (
        db_session.query(models.ProductPostings)
        .filter(models.ProductPostings.posted_by == validation1.id)
        .all()
    )
    return jsonify(
        content={
            "status": "success",
            "data": [
                {
                    "name": product.name,
                    "date_posted": product.date_posted,
                    "description": product.description,
                    "price": product.price,
                    "currency": product.currency,
                    "sold": product.sold,
                    "posted_by": f"{validation1.first_name} {validation1.last_name}",
                }
                for product in products
            ],
        }
    )


def extract_price(price_str):
    prices = re.findall(r"\d+\.\d+", price_str)
    if prices:
        return float(prices[0])
    return None


@app.route("/api/search", methods=["GET"])
def search_items_API():
    site = request.args.get("site", "all")
    item_name = request.args.get("item_name")
    min_price = float(request.args.get("min_price", 0))
    max_price = float(request.args.get("max_price", 10000))
    currency = request.args.get("currency", "USD($)")

    if not item_name:
        return jsonify({"message": "Item name is required"}), 400

    # Scrapers based on the site
    scrapers = {
        "walmart": scrape_walmart,
        "ebay": scrape_ebay,
        "bestbuy": scrape_bestbuy,
        "target": scrape_target,
    }

    # Get the appropriate scraper or all
    if site in scrapers:
        scraper_funcs = [scrapers[site]]
    else:
        scraper_funcs = scrapers.values()

    results = []
    for scraper in scraper_funcs:
        try:
            results.extend(scraper(item_name))
        except Exception as e:
            print(f"Error scraping {site}: {e}")

    # Filter results based on price range
    # filtered_results = [item for item in results if min_price <= float(item['price'].replace('$', '').replace(',', '')) <= max_price]

    try:
        filtered_results = [
            item
            for item in results
            if (price := extract_price(item["price"])) is not None
            and min_price <= price <= max_price
        ]
    except Exception as e:
        print(f"Error filtering results: {e}")
        return jsonify({"error": "Error filtering results"}), 500

    return jsonify(filtered_results)


def scrape_walmart(item_name: str) -> list[dict]:
    # Example Walmart scraping logic
    # Note: You should replace the URL and parsing logic with the actual website structure
    url = f"https://www.walmart.com/search/?q={item_name}"
    response = requests.get(url)
    print("response: ", response)
    soup = BeautifulSoup(response.text, "html.parser")
    items = []

    # for product in soup.select('.search-result-gridview-item'):
    #     title = product.select_one('.product-title').get_text(strip=True)
    #     price = product.select_one('.price').get_text(strip=True)
    #     link = product.select_one('.product-title a')['href']
    #     img_link = product.select_one('img')['src']
    #     items.append({'title': title, 'price': price, 'link': link, 'website': 'Walmart', 'img_link': img_link})

    # return items
    results = []
    print("Soup: ", soup)
    for item in soup.select("div.data-item-id"):
        title = item.select_one("div.span.lh-title")
        price = item.select_one("div.lh-copy")
        link = item.select_one(".s-item__link")

        if title and price and link:
            results.append(
                {
                    "title": title.get_text(strip=True),
                    "price": price.get_text(strip=True),
                    "link": link["href"],
                    "website": "eBay",
                }
            )
    print("items from walmart: ", results)
    return results


def scrape_target(item_name):
    url = f"https://www.target.com/s?searchTerm={item_name}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    products = soup.select(
        'div[data-test="product-grid"] section[class^="styles__StyledRowWrapper"] div[class^="styles__StyledCardWrapper"]'
    )
    print("products: ", products)
    for item in products:
        title = item.select_one(
            'div[data-test="product-details"] a[data-test="product-title"]'
        )
        price = item.select_one(
            'div[data-test="product-details"] span[data-test="current-price"]'
        )
        link = item.select_one(
            'div[data-test="product-details"] a[data-test="product-title"]'
        )

        if title and price and link:
            results.append(
                {
                    "title": title.text.strip() if title else None,
                    "price": price.text.strip() if price else None,
                    "link": "https://www.target.com" + link["href"],
                    "website": "Target",
                }
            )
    print("res from target: ", results)
    return results


def scrape_ebay(item_name):
    url = f"https://www.ebay.com/sch/i.html?_nkw={item_name}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    results = []

    for item in soup.select(".s-item"):
        title = item.select_one(".s-item__title")
        price = item.select_one(".s-item__price")
        link = item.select_one(".s-item__link")
        image_tag = item.select_one("img")
        if title and price and link:
            print("title", title)
            if title.get_text(strip=True) != "Shop on eBay":
                results.append(
                    {
                        "title": title.get_text(strip=True),
                        "price": price.get_text(strip=True),
                        "link": link["href"],
                        "img_link": image_tag["src"],
                        "website": "eBay",
                    }
                )
    print("result from Ebay: ", results)
    return results


def scrape_bestbuy(item_name):
    url = f"https://www.bestbuy.com/site/searchpage.jsp?str={item_name}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    results = []
    print("Soup: ", soup)
    for item in soup.select(".sku-item"):
        title = item.select_one("h4.sku-title a")
        price = item.select_one("div.priceView-customer-price span")
        link = item.select_one(".sku-header a")
        img_link = item.select_one("div.shop-sku-list-item div div a img")

        if title and price and link:
            results.append(
                {
                    "title": title.get_text(strip=True),
                    "price": price.get_text(strip=True),
                    "link": "https://www.bestbuy.com" + link["href"],
                    "img_link": img_link,
                    "website": "BestBuy",
                }
            )

    print("res from bestbuy", results)
    return results


@app.route("/api/wishlist", methods=["POST"])
def add_to_wishlist():
    item = request.json.get("item")
    username = request.json.get("username")
    existing_item = (
        db_session.query(models.PriceTrackProducts)
        .filter(models.PriceTrackProducts.product_url == item.get("link"))
        .first()
    )
    user = (
        db_session.query(models.Users).filter(models.Users.username == username).first()
    )
    if not existing_item:
        existing_item = models.PriceTrackProducts(
            product_name=item.get("title"),
            product_url=item.get("link"),
            site=item.get("website"),
            price=float(re.sub(r"[^0-9.]", "", item.get("price")[1:])),
            currency=item.get("price"),
            img_url=item.get("img_link"),
        )
        db_session.add(existing_item)
        db_session.commit()
        db_session.refresh(existing_item)
    wishlist_item = models.Wishlist(
        product_id=existing_item.id,
        user_id=user.id,
        product_type="online",
        date_added=datetime.now().strftime("%Y-%m-%d"),
    )
    db_session.add(wishlist_item)
    db_session.commit()
    return jsonify({"message": "Item added to wishlist successfully! "}), 200


@app.route("/api/wishlist/<product_id>", methods=["DELETE"])
def remove_from_wishlist(product_id):

    existing_item = (
        db_session.query(models.Wishlist)
        .filter(models.Wishlist.id == product_id)
        .first()
    )
    if not existing_item:
        return jsonify({"message": "Item not found in wishlist"}), 404
    db_session.delete(existing_item)
    db_session.commit()
    return jsonify({"message": "Item removed from wishlist successfully! "}), 200


@app.route("/api/wishlist/<username>", methods=["GET"])
def get_wishlist(username):
    user = (
        db_session.query(models.Users).filter(models.Users.username == username).first()
    )
    if not user:
        return jsonify({"message": "User not found"}), 404
    wishlist_objects = (
        db_session.query(models.Wishlist)
        .filter(models.Wishlist.user_id == user.id)
        .all()
    )
    wishlist = []
    for w in wishlist_objects:
        print(w.product_id)
        product = (
            db_session.query(models.PriceTrackProducts)
            .filter(models.PriceTrackProducts.id == w.product_id)
            .first()
        )
        wishlist.append(
            {
                "id": w.id,
                "user_id": w.user_id,
                "title": product.product_name,
                "price": product.price,
                "link": product.product_url,
                "website": product.site,
                "img_link": product.img_url,
            }
        )
    return jsonify(wishlist), 200


@app.route("/add-posting", methods=["POST"])
def add_posting():

    name = request.json.get("name")
    description = request.json.get("description")
    price = request.json.get("price")
    currency = request.json.get("currency")
    username = request.json.get("username")
    today_date = datetime.today().strftime("%Y-%m-%d")

    validation1 = (
        db_session.query(models.Users).filter(models.Users.username == username).first()
    )
    if validation1 is None:
        return jsonify(
            content={"status": "error", "message": f"User {username} does not exist"}
        )

    new_product = models.ProductPostings(
        name=name,
        description=description,
        price=price,
        currency=currency,
        date_posted=today_date,
        posted_by=validation1.id,
        sold=False,
    )
    db_session.add(new_product)
    db_session.commit()

    return jsonify(
        content={
            "status": "success",
        }
    )


@app.route("/send-email/<email>")
def send_email(email, content):
    print("Sending Email for user: ", email)
    msg = Message("Price drop alert", recipients=[email])
    msg.body = content
    print("Email msg: ", msg.body)
    try:
        mail.send(msg)
        print("Email sent: ", msg)
        return f"Email sent to {email}!"
    except Exception as e:
        print(str(e))
        return str(e)


@app.route("/api/price-drop-alert", methods=["POST"])
def send_price_drop_alert():
    username = request.json.get("username")
    user = (
        db_session.query(models.Users).filter(models.Users.username == username).first()
    )
    # print("Hello user: ", user.id)
    existing_wishlist = (
        db_session.query(models.Wishlist)
        .filter(models.Wishlist.user_id == user.id)
        .first()
    )
    alert_items = []
    if existing_wishlist:
        linked_products = db_session.query(models.PriceTrackProducts).filter(
            models.PriceTrackProducts.id == existing_wishlist.product_id
        )
        for product in linked_products:
            # print("Product name: ",product.product_name)
            saved_price = product.price
            # print("Product price: ", saved_price)
            current_results = scrape_ebay(product.product_name)
            # print("Current res: ", current_results)
            for item in current_results:
                curr_price = extract_price(item.get("price"))
                if curr_price is not None:
                    if curr_price < saved_price:
                        # print("Current price: ",curr_price)
                        item["price"] = str(curr_price)
                        alert_items.append(item)

        print("total alert items: ", len(alert_items))

    send_email(user.email, alert_items)
    return jsonify({"message": "User alerted about price drop successfully! "}), 200


@app.route("/login", methods=["POST"])
def login():
    username = request.json.get("username")
    password = request.json.get("password")

    user = (
        db_session.query(models.Users).filter(models.Users.username == username).first()
    )

    if user is None:
        return jsonify(content={"status": "error", "message": "User does not exist"})

    if not verify_password(password, user.hashed_password):
        return jsonify(
            content={
                "status": "error",
                "message": "Invalid password",
            }
        )

    return jsonify(
        content={
            "status": "success",
            "message": "User successfully logged in",
            "data": {
                "username": user.username,
                "email": user.email,
                "firstname": user.first_name,
                "lastname": user.last_name,
            },
        }
    )


@app.route("/register", methods=["POST"])
def register_user():
    username = request.json.get("username")
    email = request.json.get("email")
    firstname = request.json.get("firstname")
    lastname = request.json.get("lastname")
    password = request.json.get("password")

    validation1 = (
        db_session.query(models.Users).filter(models.Users.username == username).first()
    )

    validation2 = (
        db_session.query(models.Users).filter(models.Users.email == email).first()
    )

    if validation1 is not None:
        return jsonify(content={"status": "error", "message": "Username already taken"})
    if validation2 is not None:
        return jsonify(content={"status": "error", "message": "Email-id already taken"})

    user_model = models.Users()
    user_model.username = username
    user_model.email = email
    user_model.first_name = firstname
    user_model.last_name = lastname
    hash_password = get_hashed_password(password)
    user_model.hashed_password = hash_password
    db_session.add(user_model)
    db_session.commit()

    return jsonify(
        content={
            "status": "success",
            "message": "User successfully created",
            "data": {
                "username": username,
                "email": email,
                "firstname": firstname,
                "lastname": lastname,
            },
        }
    )


models.Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    app.run(debug=True)
