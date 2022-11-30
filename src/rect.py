""" Rectangle classes.
  Rect is the base class, holding only a rectangle (top, bottom, left, right).
  It also has 'contains' methods to test if a given rectangle is inside.
  DicomRect is a subclass which also holds frame, overlay properties.
  It also overrides the 'contains' method to check frame,overlay match.
  DicomOcrRect is a subclass which also holds output from OCR and NER
  tests for PII.
"""

class Rect:
    """ Holds one rectangle.
    Coordinates start at 0, top left.
    Negative coordinates represent a null/invalid rectangle.
    """
    def __init__(self, top = -1, bottom = -1, left = -1, right = -1):
        self.top, self.bottom, self.left, self.right = top, bottom, left, right

    def __repr__(self):
        return '<Rect %d,%d->%d,%d>' % (self.left, self.top, self.right, self.bottom)

    def set_rect(self, t, b, l, r):
        self.top, self.bottom, self.left, self.right = t, b, l, r

    def get_rect(self):
        return self.top, self.bottom, self.left, self.right

    def ltrb(self):
        return (self.left, self.top, self.right, self.bottom)

    def ltwh(self):
        return (self.left, self.top, 1 + self.right - self.left, 1 + self.bottom - self.top)

    def T(self):
        return self.top
    def B(self):
        return self.bottom
    def L(self):
        return self.left
    def R(self):
        return self.right

    def contains(self, x, y):
        """ Check if the given coordinate is inside this rectangle.
        """
        inside = (x >= self.left and x <= self.right and y >= self.top and y <= self.bottom)
        return inside

    def contains_rect(self, other_rect):
        """ Check if the given rectangle is fully inside (or equal to) this rectangle.
        """
        t,b,l,r = other_rect.get_rect()
        return self.contains(l, t) and self.contains(r, b)


# ---------------------------------------------------------------------

class DicomRect(Rect):
    """ Holds one rectangle and which image frame/overlay it applies to.
    Coordinates start at 0, top left.
    -1 means unset or not applicable for frame/overlay number.
    Overlay = -1 means frame is a standard frame.
    Overlay >= 0 means frame is within that overlay.
    """
    def __init__(self, top = None, bottom = None, left = None, right = None, frame = -1, overlay = -1):
        super().__init__(top, bottom, left, right)
        self.frame, self.overlay = frame, overlay

    def __repr__(self):
        return '<DicomRect frame=%d overlay=%d %d,%d->%d,%d>' % (self.frame, self.overlay, self.left, self.top, self.right, self.bottom)

    def F(self):
        return self.frame

    def O(self):
        return self.overlay

    def contains(self, x, y, frame = -1, overlay = -1):
        """ Check if the given coordinate is inside this rectangle,
        and the frame,overlay, if given, match this object.
        """
        rc = True
        if frame != -1 and frame != self.frame: rc = False
        if overlay != -1 and overlay != self.overlay: rc = False
        if not super().contains(x,y): rc = False
        return rc


# ---------------------------------------------------------------------

def add_Rect_to_list(rectlist, addrect):
    """ Extend the given list of rectangles with the given rectangle.
    Works with Rect or DicomRect objects.
    """
    # If this one is larger we need to remove ALL smaller rects from the existing list
    rectlist[:] = [
        rect for rect in rectlist if
            not addrect.contains_rect(rect)
    ]
    # Now add the new one if it's not smaller than an existing one
    for rect in rectlist:
        # If a larger rectangle already exists then ignore this one
        if rect.contains_rect(addrect):
            continue
    rectlist.append(addrect)


# ---------------------------------------------------------------------

def test_rect():
    r = Rect(1, 11, 2, 12)
    assert r.ltrb() == (2, 1, 12, 11)
    d = DicomRect(3, 33, 4, 44, 9, 10)
    assert d.F() == 9
    assert d.O() == 10
    d2 = DicomRect(4, 30, 5, 40)
    assert(r.contains(5,5) == True)
    assert(d.contains(5,5) == True)
    assert(d.contains(5,5) == True)
    assert(d.contains(5,5, 8, 8) == False)
    assert(d.contains(5,5, 9, 10) == True)
    assert(r.contains_rect(d) == False)
    assert(d.contains_rect(d2) == True)
    assert(d2.contains_rect(d) == False)
    list1 = []
    list2 = []
    add_Rect_to_list(list1, r)
    add_Rect_to_list(list1, d)
    add_Rect_to_list(list1, d2)
    print(list1)
    add_Rect_to_list(list2, r)
    add_Rect_to_list(list2, d2)
    add_Rect_to_list(list2, d)
    print(list2)
    assert(len(list1) == 2)
    assert(len(list2) == 2)
