# SistemPenyiramTanaman-Tsukamoto
source code sistem penyiram tanaman dengan bahasa python untuk raspberry pi, dengan sensor kelembapan tanah, sensor hujan, sensor suhu dht22, mcp3008, dan relay 4-channel

Sistem penyiraman tanaman dengan menggunakan raspberry pi 3 model b+
Membaca data dari sensor kelembapan tanah(analog), sensor suhu dht22(digital), dan sensor hujan(analog)
Sensor analog dibaca menggunakan adc MCP3008
Data sensor diolah menggunakan logika fuzzy Tsukamoto untuk menentukan penyiraman
Data sensor dan penyiraman dikirim ke nodeRED melalui mosquitto mqtt
