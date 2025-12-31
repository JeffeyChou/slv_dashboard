from flask import Flask, render_template, jsonify
from data_fetcher import SilverDataFetcher

app = Flask(__name__)
fetcher = SilverDataFetcher()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    data = fetcher.get_all_data()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
