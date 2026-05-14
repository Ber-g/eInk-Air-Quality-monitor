A vibrant, highly concentrated 4" (640 x 400 pixel) 7 colour electronic paper display for Raspberry Pi.

New ePaper screens just keep getting better! We can't resist them with their delicious crispness, impressive low power credentials and enticing viewing angles (even in bright sunlight). This 4" eInk display is positively bulging with pixel density and bright strong colours, and we've fitted it with all the necessary apparatus to interface with a Raspberry Pi cleanly, humanely and without fuss.

Inky Impression 4" is comparable in size to our 3 colour Inky wHAT, but it's got a number of advantages over ol' wHATty:

    Seven glorious colours to play with!
    Crammed with over double the pixels (256,000 vs 120,000)!
    Four side mounted buttons that remain accessible whilst wall mounted!

eInk displays only consume power whilst refreshing, so they're a good choice for things like home automation dashboards and calendar displays that are always on. We've found these 7 colour displays do a really nice job of displaying art too - especially stylised, bold images like pop art and children's drawings.

This screen takes around 15 seconds to refresh, so is best suited to projects that don't rely on constant screen updates. Please note that it's not possible to change the colour of the purple border on this screen using software, like with some Inky displays.
Features

    4.01" EPD display (640 x 400 pixels)
        E Ink Gallery Palette™ ePaper
        ACeP (Advanced Color ePaper) 7-color with black, white, red, green, blue, yellow, orange
        Ultra wide viewing angles
        Ultra low power consumption
        Dot pitch – 0.135 x 0.135mm
    40-pin female header included to boost height for full-size Pis
    Standoffs included to securely attach to your Pi
    I2C pins broken out for adding breakouts
    Compatible with all 40-pin header Raspberry Pi models*
    Python library
    Comes fully assembled

Multi-colour EPD displays use electrophoresis to pull coloured particles up and down on the display. The coloured particles reflect light, unlike most display types, meaning that they're visible under bright lights. It takes approximately 15 seconds to refresh the display.

Everything comes fully-assembled, and there's no soldering required! The display is securely stuck down to the Inky Impression PCB and connected via a ribbon cable. Just pop Inky Impression on your Pi and run our installer to get everything set up!

We've also broken out the I2C pins on the back of Inky Impression, letting you connect additional devices like breakouts and show their data right on the display.

Inky Impression will work with any version of the Pi with a 40 pin header, including Zero variants. If you want to use it with a Raspberry Pi 400, you'll probably also want to get a GPIO extender cable (unless you're into using screens at a highly unusual angle).
Software

The Python library takes the stress out of displaying text and images on Inky Impression, and we've put together a few new examples to show off Inky Impression's capabilities. We've put together a one-line-installer for the Python library too, to make installation a little more straightforward:

curl https://get.pimoroni.com/inky | bash
Notes

    The Inky Impression display is made from glass so it's pretty fragile. Be careful not to drop it or press too hard on it, or it will crack. When fitting it to your Pi, grip at the edges of the board rather than pressing on top of the screen.
    ePaper displays work best when refreshed at an ambient room temperature, if the screen is cold you might find that the colours are less vibrant.
    Overall display dimensions: 97 x 69mm (W x H)
    Display usable area dimensions: 86 x 54mm (WxH)
    Photo by Steve Johnson from Pexels
