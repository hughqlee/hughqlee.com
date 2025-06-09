import re
import os

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import urlparse

from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 데이터베이스 파일은 실행 디렉토리에 database.db로 생성됨.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Counter(db.Model):
    __tablename__ = 'counter'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    count = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Counter {self.username}>'

@app.route('/', methods=['GET'])
def index():
    return render_template('main.html')

@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    """사이트맵 XML 파일을 제공하는 라우트"""
    return render_template('sitemap.xml'), 200, {'Content-Type': 'application/xml'}

@app.route('/robots.txt', methods=['GET'])
def robots():
    """검색 엔진 크롤러를 위한 robots.txt 파일을 제공하는 라우트"""
    return render_template('robots.txt'), 200, {'Content-Type': 'text/plain'}

@app.route('/ads.txt', methods=['GET'])
def ads():
    return render_template('ads.txt'), 200, {'Content-Type': 'text/plain'}

@app.route('/brickbreaker', methods=['GET'])
def brickbreaker():
    return render_template('brickbreaker.html')

@app.route('/squardshuffler', methods=['GET'])
def squardshuffler():
    return render_template('squardshuffler.html')

@app.route('/tool4img', methods=['GET'])
def tool4img():
    return render_template('tool4img.html')

@app.route('/landing4everyone', methods=['GET'])
def landing4everyone():
    return render_template('landing4everyone.html')

@app.route('/nine', methods=['GET'])
def nine():
    return render_template('nine.html')

@app.route('/goaltracker', methods=['GET'])
def goaltracker():
    return render_template('goaltracker.html')

# API

@app.route('/api/tts', methods=['POST'])
def tts():    
    data = request.json
    text = data.get('text')
    
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="sage",
        input=text,
        instructions="4세 아이의 인형 친구가 되어줘. 귀여운 말투로 한국어를 유창하게 구사해줘."
    )
    
    return Response(
        response.content,
        mimetype='audio/wav',
        headers={
            'Content-Disposition': 'attachment; filename=speech.wav'
        }
    )

@app.route('/api/v1/action', methods=['GET', 'POST'])
def action():
    if request.method == 'GET':
        counters = Counter.query.all()
        data = [{'username': counter.username, 'count': counter.count} for counter in counters]
        return jsonify(data)
    elif request.method == 'POST':
        # 요청 헤더에서 Origin 값 가져오기
        origin = request.headers.get("Origin")
        if not origin:
            return jsonify({"error": "Missing Origin header"}), 400
        
        # 정규식을 사용하여 GitHub Pages URL에서 username 추출
        match = re.match(r"https?://([a-zA-Z0-9\-]+)\.github\.io", origin)
        
        if match:
            # 매칭된 username 반환
            username = match.group(1)
            counter = Counter.query.filter_by(username=username).first()
            if counter:
                counter.count += 1
            else:
                counter = Counter(username=username, count=1)
                db.session.add(counter)
            db.session.commit()
            return jsonify({'username': counter.username, 'count': counter.count})
        else:
            # URL 형식이 올바르지 않은 경우 오류 반환
            return jsonify({"error": "Invalid Origin format"}), 400

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 테이블이 없으면 생성합니다.
    app.run(debug=False)