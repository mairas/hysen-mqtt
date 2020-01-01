# hysen-mqtt: MQTT gateway for Hysen Floor Thermostats

## About

`hysen-mqtt` provides a Hass.io addon for running an MQTT gateway for Hysen floor thermostats.

Hysen floor thermostats are very inexpensive Chinese wall-mounted thermostat units supporting external NTC temperature sensors and up to 16 A of heating current. They are sold on multiple brands such as Anself, Beok, Floureon or Decdeal. The devices are based on a Broadlink chipset. The manufacturer provides a rudimentary phone app for both Android and iOS.

There exist some bindings for common OSS home automation software--I myself, among others, have worked on the [Home Assistant binding](https://github.com/mairas/hysen). For Home Assistant, in particular, the binding has not been merged to the main project, and I remain hesitant to do so because of the exotic protocol, implied maintenance burden and other factors.

I recently converted my open Home Assistant installation to the fully Dockerized Hass.io platform. Instead of adding the custom binding component to the Home Assistant process, I thought it would be a good idea to implement it as a separate microservice, using MQTT as the API. That way, if the Home Assistant internal APIs change, the Hysen gateway will be unaffected, and, more importantly, if/when there are stability issues in the Hysen binding, they won't affect the whole Home Assistant installation.

I recently found [an existing project](https://github.com/ralphm2004/broadlink-thermostat) with very similar goals, but targeting OpenHAB integration instead. It probably would be quite easy to wrap that project into a Hass.io addon with the same end result.

## Installation

Until the addon is available in the community addon store, it has to be installed manually.

1.  Clone the Github repository to your Hass.io 
    `/addons` directory:

        cd /addons
        git clone https://github.com/mairas/hysen-mqtt

2.  Navigate to your Hass.io installation's Add-on store and click the refresh button at the top-right of the page. You should see a separate section titled "Local add-ons". Open "Hysen MQTT Gateway" and click "Install". Once the spinner stops rotating, the add-on has been installed.

## Configuration

The following configuration options are supported:

| Name | Description |
| ---- | ----------- |
| `mqtt_host` | The hostname of your MQTT server. For typical local installations, `localhost` should work fine. |
| `mqtt_port` | The default is 1883. |
| `mqtt_user` | A username for authenticating to the MQTT host. |
| `mqtt_password` | A password for authenticating to the MQTT host. |
| `local_ip_address` | The local public IP address of your Hass.io installation. This is used to determine the interface used for broadcasting the broadlink discovery packages. Typically something like `192.168.1.100`. |
