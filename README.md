Pentest Arsenal

Koleksi tools penetration testing, diorganisir per kategori tim.
Maintained by @dukunline-cyber


Struktur Direktori

recon/          - Reconnaissance & information gathering
scanning/       - Port scanning, vulnerability scanning
web-attack/     - Web application attack tools
network-attack/ - Network exploitation, lateral movement
exploitation/   - Exploit frameworks & payload generators
post-exploitation/ - Privilege escalation, persistence, exfiltration
osint/          - Open source intelligence gathering
wordlists/      - Password lists, directory lists, fuzzing payloads
reporting/      - Report generation & documentation tools
utilities/      - Helper scripts, encoders, misc tools


Install

Tiap folder ada install.sh untuk setup tools di kategori itu.

  cd recon && bash install.sh

Atau install semua sekaligus:

  bash install-all.sh


Tools List

Recon
- reconftw - Automated recon framework
- subfinder - Subdomain discovery
- amass - Attack surface mapping
- httpx - HTTP probing

Scanning
- naabu - Fast port scanner
- nuclei - Vulnerability scanner
- nikto - Web server scanner
- whatweb - Web technology identifier

Web Attack
- feroxbuster - Directory brute forcer
- sqlmap - SQL injection automation
- xsstrike - XSS detection
- dalfox - XSS scanner

Network Attack
- netexec - Network execution & lateral movement
- responder - LLMNR/NBT-NS/MDNS poisoner
- impacket - Network protocol tools
- chisel - TCP/UDP tunneling

Exploitation
- metasploit-framework - Exploit framework
- searchsploit - Exploit database search
- hexstrike-ai - AI-powered pentest agents

Post Exploitation
- linpeas - Linux privilege escalation
- winpeas - Windows privilege escalation
- pspy - Process snooping
- ligolo-ng - Tunneling/pivoting

OSINT
- mosint - Email OSINT
- sherlock - Username hunting
- theHarvester - Email/subdomain/IP gathering
- spiderfoot - OSINT automation

Wordlists
- SecLists - Collection of security lists
- rockyou - Classic password list
- dirbuster - Directory wordlists

Reporting
- pwndoc - Pentest report generator
- sysreptor - Pentest reporting platform

Utilities
- cyberchef - Data encoding/decoding
- jwt-tool - JWT testing
- hashcat - Password cracking
- john - John the Ripper



