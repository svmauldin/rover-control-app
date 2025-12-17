[200~"""
Rover Control Android App
- Voice commands
- Animated face (landscape mode)
- Face detection
- Text-to-speech
- WebSocket communication with rover
"""

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Ellipse, Line
from kivy.clock import Clock
from kivy.core.window import Window
import json
import asyncio
from threading import Thread

# Set landscape orientation
Window.orientation = 'landscape'

# WebSocket connection (we'll use websockets library)
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("websockets not available")

# Android-specific imports
try:
    from android.permissions import request_permissions, Permission
    from jnius import autoclass
    ANDROID = True
    
    # Java classes for Android
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    RecognizerIntent = autoclass('android.speech.RecognizerIntent')
    
except ImportError:
    ANDROID = False
    print("Not running on Android")


class RoverFace(Widget):
    """Animated face widget"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expression = 'normal'
        self.eye_color = (0, 1, 0, 1)  # Green
        self.blink_counter = 0
        self.eye_height = 80
        
        # Schedule animation
        Clock.schedule_interval(self.update, 1/30.0)  # 30 FPS
        
    def update(self, dt):
        self.canvas.clear()
        
        # Blinking animation
        self.blink_counter += 1
        if self.blink_counter > 60:
            self.eye_height = max(5, self.eye_height - 10)
            if self.eye_height <= 5:
                self.blink_counter = 0
        elif self.eye_height < 80:
            self.eye_height = min(80, self.eye_height + 10)
        
        self.draw_face()
        
    def draw_face(self):
        with self.canvas:
            # Background
            Color(0, 0, 0, 1)
            
            # Eyes
            Color(*self.eye_color)
            
            # Left eye
            left_x = self.width * 0.35
            left_y = self.height * 0.5
            Ellipse(pos=(left_x - 40, left_y - self.eye_height/2), 
                   size=(80, self.eye_height))
            
            # Right eye
            right_x = self.width * 0.65
            right_y = self.height * 0.5
            Ellipse(pos=(right_x - 40, right_y - self.eye_height/2), 
                   size=(80, self.eye_height))
            
            # Eyebrows based on expression
            self.draw_eyebrows(left_x, left_y, right_x, right_y)
    
    def draw_eyebrows(self, lx, ly, rx, ry):
        with self.canvas:
            Color(*self.eye_color)
            
            if self.expression == 'happy':
                Line(points=[lx-50, ly-60, lx+50, ly-70], width=4)
                Line(points=[rx-50, ry-70, rx+50, ry-60], width=4)
            elif self.expression == 'angry':
                Line(points=[lx-40, ly-70, lx+50, ly-50], width=4)
                Line(points=[rx-50, ry-50, rx+40, ry-70], width=4)
            elif self.expression == 'surprised':
                Line(circle=(lx, ly-70, 30, 0, 180), width=4)
                Line(circle=(rx, ry-70, 30, 0, 180), width=4)
            elif self.expression == 'sad':
                Line(points=[lx-50, ly-50, lx+50, ly-60], width=4)
                Line(points=[rx-50, ry-60, rx+50, ry-50], width=4)
    
    def change_expression(self, expr, color=None):
        self.expression = expr
        if color:
            self.eye_color = color
        else:
            # Default colors for expressions
            colors = {
                'happy': (0, 1, 0, 1),      # Green
                'angry': (1, 0, 0, 1),      # Red
                'surprised': (1, 1, 0, 1),  # Yellow
                'sad': (0, 0.5, 1, 1),      # Blue
                'normal': (0, 1, 0, 1)      # Green
            }
            self.eye_color = colors.get(expr, (0, 1, 0, 1))


class RoverControlApp(App):
    """Main application"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ws = None
        self.ws_connected = False
        self.rover_ip = "192.168.0.27"
        self.rover_port = 8765
        
    def build(self):
        # Request permissions on Android
        if ANDROID:
            request_permissions([
                Permission.RECORD_AUDIO,
                Permission.CAMERA,
                Permission.INTERNET
            ])
        
        # Main layout
        root = BoxLayout(orientation='horizontal')
        
        # Left side - Face
        self.face = RoverFace()
        root.add_widget(self.face)
        
        # Right side - Controls
        control_panel = BoxLayout(orientation='vertical', size_hint=(0.3, 1))
        
        # Status label
        self.status_label = Label(
            text='Status: Connecting...',
            size_hint=(1, 0.1),
            color=(1, 1, 1, 1)
        )
        control_panel.add_widget(self.status_label)
        
        # Control buttons
        btn_forward = Button(text='Forward', size_hint=(1, 0.15))
        btn_forward.bind(on_press=lambda x: self.send_command('forward'))
        control_panel.add_widget(btn_forward)
        
        btn_backward = Button(text='Backward', size_hint=(1, 0.15))
        btn_backward.bind(on_press=lambda x: self.send_command('backward'))
        control_panel.add_widget(btn_backward)
        
        btn_left = Button(text='Left', size_hint=(1, 0.15))
        btn_left.bind(on_press=lambda x: self.send_command('left'))
        control_panel.add_widget(btn_left)
        
        btn_right = Button(text='Right', size_hint=(1, 0.15))
        btn_right.bind(on_press=lambda x: self.send_command('right'))
        control_panel.add_widget(btn_right)
        
        btn_stop = Button(text='STOP', size_hint=(1, 0.15))
        btn_stop.bind(on_press=lambda x: self.send_command('stop'))
        control_panel.add_widget(btn_stop)
        
        # Voice button
        btn_voice = Button(text='🎤 Voice', size_hint=(1, 0.15))
        btn_voice.bind(on_press=self.start_voice_recognition)
        control_panel.add_widget(btn_voice)
        
        root.add_widget(control_panel)
        
        # Start WebSocket connection
        Thread(target=self.connect_websocket, daemon=True).start()
        
        return root
    
    def connect_websocket(self):
        """Connect to rover via WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            self.update_status("WebSocket not available")
            return
            
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        
        try:
            loop.run_until_complete(self.websocket_handler())
        except Exception as e:
            print(f"WebSocket error: {e}")
            self.update_status(f"Error: {e}")
    
    async def websocket_handler(self):
        """Handle WebSocket connection"""
        uri = f"ws://{self.rover_ip}:{self.rover_port}"
        
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    self.ws = ws
                    self.ws_connected = True
                    self.update_status("Connected ✅")
                    
                    # Listen for messages
                    async for message in ws:
                        data = json.loads(message)
                        if data.get('type') == 'command_result':
                            self.speak(data.get('message', ''))
                            
            except Exception as e:
                self.ws_connected = False
                self.update_status(f"Disconnected ❌")
                await asyncio.sleep(5)  # Retry after 5 seconds
    
    def send_command(self, command):
        """Send voice command to rover"""
        if self.ws and self.ws_connected:
            message = {
                'type': 'voice_command',
                'command': command
            }
            
            # Change face based on command
            if command in ['forward', 'go']:
                self.face.change_expression('happy')
            elif command == 'stop':
                self.face.change_expression('normal')
            elif command in ['backward', 'back']:
                self.face.change_expression('surprised')
            elif command in ['left', 'right']:
                self.face.change_expression('cute')
            
            # Send via WebSocket
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(message)),
                asyncio.get_event_loop()
            )
            print(f"Sent command: {command}")
        else:
            self.update_status("Not connected!")
            self.speak("Not connected to rover")
    
    def start_voice_recognition(self, instance):
        """Start Android voice recognition"""
        if not ANDROID:
            self.update_status("Voice only on Android")
            return
            
        try:
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                          RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Say a command")
            
            PythonActivity.mActivity.startActivityForResult(intent, 1234)
            self.face.change_expression('surprised')
            self.speak("Listening")
            
        except Exception as e:
            print(f"Voice recognition error: {e}")
            self.update_status(f"Voice error: {e}")
    
    def on_activity_result(self, request_code, result_code, intent):
        """Handle voice recognition result"""
        if request_code == 1234:
            if result_code == -1:  # RESULT_OK
                results = intent.getStringArrayListExtra(
                    RecognizerIntent.EXTRA_RESULTS)
                if results:
                    command = results.get(0).lower()
                    print(f"Voice command: {command}")
                    self.send_command(command)
    
    def speak(self, text):
        """Text-to-speech"""
        if ANDROID:
            try:
                TTS = autoclass('android.speech.tts.TextToSpeech')
                tts = TTS(PythonActivity.mActivity, None)
                tts.speak(text, TTS.QUEUE_FLUSH, None, None)
            except Exception as e:
                print(f"TTS error: {e}")
        else:
            print(f"Would speak: {text}")
    
    def update_status(self, text):
        """Update status label"""
        def update(dt):
            self.status_label.text = f"Status: {text}"
        Clock.schedule_once(update, 0)


if __name__ == '__main__':
    RoverControlApp().run()
