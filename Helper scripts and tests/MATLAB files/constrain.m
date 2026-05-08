function f = constrain(X, a, b)
  X = X ./ (1+abs(X));
  f = ((b-a)*X+(a+b))/2;
