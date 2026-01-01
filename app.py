from flask import Flask, render_template, jsonify, request
from data_fetcher import SilverDataFetcher

app = Flask(__name__)
fetcher = SilverDataFetcher()
# Run backfill on startup
fetcher.backfill_history()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    data = fetcher.get_all_data_and_store()
    return jsonify(data)

@app.route('/api/history')
def get_history():
    metric = request.args.get('metric')
    days = request.args.get('days', default=30, type=int)
    
    if not metric:
        return jsonify({'error': 'metric parameter required'}), 400
        
    history = fetcher.storage.get_history(metric, days=days)
    return jsonify(history)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
