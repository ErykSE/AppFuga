import threading
import time
import requests

class HeartbeatTagSender:
    def __init__(self, api_base_url, info_logger, error_logger, verify_ssl=False):
        self.api_base_url = api_base_url
        self.info_logger = info_logger
        self.error_logger = error_logger
        self.verify_ssl = verify_ssl
        
        # Konfiguracja
        self.heartbeat_interval = 1.0  # co sekundę
        self.heartbeat_value = 0  # licznik który się zwiększa
        
        # Threading - to będzie działać w osobnym wątku!
        self.heartbeat_thread = None
        self.stop_event = threading.Event()
        self.is_running = False
    
    def start(self):
        """Uruchamia heartbeat tag sender."""
        if self.is_running:
            return
            
        self.info_logger.info("Starting heartbeat tag sender (every 1 second)")
        self.is_running = True
        
        # Tworzy NOWY WĄTEK - niezależny od algorytmu!
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
    
    def stop(self):
        """Zatrzymuje heartbeat."""
        if not self.is_running:
            return
            
        self.info_logger.info("Stopping heartbeat tag sender")
        self.stop_event.set()
        self.is_running = False
        
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=2)
    
    def _heartbeat_loop(self):
        """Główna pętla - DZIAŁA W OSOBNYM WĄTKU!"""
        while not self.stop_event.wait(self.heartbeat_interval):
            self._send_heartbeat_tag()
    
    def _send_heartbeat_tag(self):
        """Wysyła heartbeat tag do SCADA."""
        self.heartbeat_value += 1
        
        if self.heartbeat_value > 1000:
            self.heartbeat_value = 1
        
        url = f"{self.api_base_url}/api/Scada/heartbeat-tag"
        payload = {"value": self.heartbeat_value}
        
        try:
            response = requests.post(url, json=payload, verify=self.verify_ssl, timeout=2)
            response.raise_for_status()
            
            # Loguj tylko co 60 sekund
            if self.heartbeat_value % 60 == 0:
                self.info_logger.info(f"Heartbeat tag: {self.heartbeat_value}")
            
        except Exception as e:
            self.error_logger.warning(f"Heartbeat tag failed: {str(e)}")