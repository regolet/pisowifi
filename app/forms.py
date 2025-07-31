from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import re
from app import models

class ClientsForm(forms.ModelForm):
	Time_Left= forms.CharField(widget= forms.TextInput
		(attrs={'class':'vTextField'}))
	
	class Meta:
		model = models.Clients
		fields = '__all__'

class NetworkForm(forms.ModelForm):
	# IP address validator
	ip_validator = RegexValidator(
		regex=r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$',
		message='Enter a valid IP address.'
	)
	
	Server_IP = forms.CharField(
		widget=forms.TextInput(attrs={'class':'vTextField'}),
		validators=[ip_validator],
		max_length=15
	)
	Netmask = forms.CharField(
		widget=forms.TextInput(attrs={'class':'vTextField'}),
		validators=[ip_validator],
		max_length=15
	)
	DNS_1 = forms.CharField(
		widget=forms.TextInput(attrs={'class':'vTextField'}),
		validators=[ip_validator],
		max_length=15
	)
	DNS_2 = forms.CharField(
		widget=forms.TextInput(attrs={'class':'vTextField'}),
		validators=[ip_validator],
		max_length=15,
		required=False
	)
	
	class Meta:
		model = models.Network
		fields = '__all__'
	
	def clean_Server_IP(self):
		ip = self.cleaned_data.get('Server_IP')
		if ip and not self._is_valid_ip(ip):
			raise ValidationError('Invalid IP address format.')
		return ip
	
	def clean_Netmask(self):
		netmask = self.cleaned_data.get('Netmask')
		if netmask and not self._is_valid_netmask(netmask):
			raise ValidationError('Invalid netmask format.')
		return netmask
	
	def _is_valid_ip(self, ip):
		"""Validate IP address"""
		try:
			parts = ip.split('.')
			return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
		except:
			return False
	
	def _is_valid_netmask(self, netmask):
		"""Validate netmask"""
		valid_netmasks = [
			'255.255.255.0', '255.255.0.0', '255.0.0.0',
			'255.255.255.128', '255.255.255.192', '255.255.255.224',
			'255.255.255.240', '255.255.255.248', '255.255.255.252'
		]
		return netmask in valid_netmasks

class SettingsForm(forms.ModelForm):
	Base_Value = forms.CharField(
		widget=forms.TextInput(attrs={'class':'vTextField'}),
		max_length=50
	)
	Default_Block_Duration = forms.CharField(
		widget=forms.TextInput(attrs={'class':'vTextField'}),
		max_length=50
	)
	Enable_Permanent_Block = forms.BooleanField(
		required=False, 
		widget=forms.CheckboxInput(attrs={'class':'vCheckboxLabel'})
	)

	class Meta:
		model = models.Settings
		# Exclude portal-related fields as they are now handled by Portal Settings
		exclude = ['Hotspot_Name', 'Hotspot_Address', 'BG_Image', 'Vouchers_Flg', 'Pause_Resume_Flg', 'Disable_Pause_Time', 'Redir_Url', 'Slot_Timeout']

class VoucherRedeemForm(forms.Form):
	"""Secure form for voucher redemption"""
	voucher_code = forms.CharField(
		max_length=20,
		min_length=6,
		widget=forms.TextInput(attrs={
			'class': 'form-control',
			'placeholder': 'Enter voucher code',
			'pattern': '[A-Za-z0-9]+',
			'title': 'Voucher code should contain only letters and numbers'
		}),
		validators=[
			RegexValidator(
				regex=r'^[A-Za-z0-9]+$',
				message='Voucher code should contain only letters and numbers.'
			)
		]
	)
	
	def clean_voucher_code(self):
		voucher_code = self.cleaned_data.get('voucher_code')
		if voucher_code:
			voucher_code = voucher_code.strip().upper()
			# Additional validation
			if len(voucher_code) < 6:
				raise ValidationError('Voucher code must be at least 6 characters.')
			if not voucher_code.isalnum():
				raise ValidationError('Voucher code should contain only letters and numbers.')
		return voucher_code

class SecureMACForm(forms.Form):
	"""Form for MAC address input with validation"""
	mac_address = forms.CharField(
		max_length=17,
		validators=[
			RegexValidator(
				regex=r'^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$',
				message='Enter a valid MAC address (e.g., 00:11:22:33:44:55).'
			)
		],
		widget=forms.TextInput(attrs={
			'class': 'form-control',
			'placeholder': '00:11:22:33:44:55',
			'pattern': '([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})'
		})
	)
	
	def clean_mac_address(self):
		mac = self.cleaned_data.get('mac_address')
		if mac:
			# Normalize MAC address format
			mac = mac.replace('-', ':').lower()
			# Validate format
			if not re.match(r'^([0-9a-f]{2}:){5}([0-9a-f]{2})$', mac):
				raise ValidationError('Invalid MAC address format.')
		return mac